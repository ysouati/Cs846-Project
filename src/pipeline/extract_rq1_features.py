"""Pipeline script to extract Research Question 1 (RQ1) features."""

import os
import json
import argparse
from datetime import datetime
from collections import defaultdict

from src.data.huggingface_loader import HFDataLoader
from src.data.github_graphql import GitHubGraphQLClient
from src.heuristics.test_classifier import TestFileClassifier
from src.heuristics.code_churn_analyzer import CodeChurnAnalyzer


def calculate_resolution_time(created_at: str, merged_at: str) -> float:
    """Calculates PR resolution time in seconds.
    
    Args:
        created_at: ISO 8601 string of creation time.
        merged_at: ISO 8601 string of merge time (can be None).
        
    Returns:
        Float seconds if merged, else None.
    """
    if not created_at or not merged_at:
        return None
        
    try:
        # Standardize 'Z' to '+00:00' for fromisoformat
        c_fmt = created_at.replace("Z", "+00:00")
        m_fmt = merged_at.replace("Z", "+00:00")
        
        c_dt = datetime.fromisoformat(c_fmt)
        m_dt = datetime.fromisoformat(m_fmt)
        
        delta = m_dt - c_dt
        return round(delta.total_seconds(), 2)
    except ValueError:
        return None


def check_independent_ci_fix(timeline_commits: list, statuses: dict, pr_agent: str) -> bool:
    """Checks if the agent independently fixed a failing CI pipeline.
    
    A fix is valid if an earlier commit had a FAILURE/ERROR state,
    and a subsequent commit by the agent results in a SUCCESS state.
    """
    if not timeline_commits:
        return False
        
    had_failure = False
    
    for commit in timeline_commits:
        sha = commit.get("sha")
        state = statuses.get(sha, "NONE")
        
        if state in ("FAILURE", "ERROR"):
            had_failure = True
        elif state == "SUCCESS" and had_failure:
            # The pipeline failed previously, but is now passing.
            return True
            
    return False


def main():
    parser = argparse.ArgumentParser(description="Extract RQ1 Features from mapped AIDev data.")
    parser.add_argument("--input", type=str, default="modular_filtered_test_prs.json",
                        help="Path to the initial timeline JSON.")
    parser.add_argument("--output", type=str, default="rq1_metrics_dataset.json",
                        help="Path to save the output JSON.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of PRs to process sequentially (0 for all).")
    args = parser.parse_args()

    print(f"1) Loading base PR timelines from {args.input}...")
    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")
        
    with open(args.input, "r", encoding="utf-8") as f:
        pr_timelines = json.load(f)

    if args.limit > 0:
        pr_timelines = pr_timelines[:args.limit]
        print(f"   Limited processing to {args.limit} PRs.")

    pr_id_set = {str(pr["pr_id"]) for pr in pr_timelines}

    loader = HFDataLoader(dataset_name="hao-li/AIDev")
    
    print("2) Fetching Project Factors (Stars, Forks) from HF 'repository' table...")
    ds_repo = loader.load_table("repository")
    repo_meta = {}
    for r in ds_repo:
        repo_id = str(r.get('id'))
        repo_meta[repo_id] = {
            "stars": r.get('stars', 0),
            "forks": r.get('forks', 0)
        }

    # Map PRs back to repo_ids using HuggingFace PR table
    print("3) Mapping Project metadata to PRs...")
    ds_pr = loader.load_table("pull_request")
    pr_meta_map = {}
    for p in ds_pr:
        pid = str(p.get("id"))
        if pid in pr_id_set:
            repo_id = str(p.get("repo_id"))
            pr_meta_map[pid] = repo_meta.get(repo_id, {"stars": 0, "forks": 0})

    print("4) Processing 'pr_commit_details' for Test-to-Code Ratio & PR Authors...")
    ds_commit_details = loader.load_table("pr_commit_details")
    
    # Store rows per PR to send to the Churn Analyzer
    pr_rows = defaultdict(list)
    pr_authors = defaultdict(set)
    
    for row in ds_commit_details:
        pid = str(row.get("pr_id"))
        if pid in pr_id_set:
            pr_rows[pid].append(row)
            author = row.get("author")
            if author:
                pr_authors[pid].add(author)

    print("5) Resolving metrics and gathering CI statuses via GraphQL...")
    graphql_client = GitHubGraphQLClient()
    
    # Group by repository to batch fetch CI statuses efficiently
    repo_grouped_prs = defaultdict(list)
    for pr in pr_timelines:
        repo_grouped_prs[pr["repo_full_name"]].append(pr)
        
    total_repos = len(repo_grouped_prs)
    repo_counter = 0
    
    final_results = []

    for repo_fn, prs_in_repo in repo_grouped_prs.items():
        repo_counter += 1
        print(f"   [{repo_counter}/{total_repos}] Analyzing {repo_fn} ({len(prs_in_repo)} PRs)...")
        
        # Collect all unique commits needed for this repo
        repo_commit_shas = set()
        for pr in prs_in_repo:
            for commit in pr.get("commits", []):
                repo_commit_shas.add(commit["sha"])
                
        repo_commit_shas = list(repo_commit_shas)
        owner, name = repo_fn.split('/')
        
        # Fetch status logic
        commit_statuses = {}
        if repo_commit_shas:
            try:
                commit_statuses = graphql_client.fetch_commit_statuses_batch(owner, name, repo_commit_shas)
            except Exception as e:
                print(f"      [!] Warning: Failed to fetch statuses: {e}")
        
        for pr in prs_in_repo:
            pid = str(pr["pr_id"])
            
            # Code Churn & Test Ratio logic
            churn_metrics = CodeChurnAnalyzer.analyze_pr_churn(pr_rows[pid], TestFileClassifier)
            
            # Resolution time
            res_time_seconds = calculate_resolution_time(pr.get("created_at"), pr.get("merged_at"))
            
            # CI Agent Fixing metric
            indep_fix = check_independent_ci_fix(pr.get("commits", []), commit_statuses, pr.get("agent_type"))
            
            # Assemble the RQ1 payload
            feature_obj = {
                "pr_id": pr["pr_id"],
                "pr_number": pr["pr_number"],
                "repo_full_name": pr["repo_full_name"],
                "agent_type": pr["agent_type"],
                
                # Part 1: Agent Behaviors
                "dominant_test_type": churn_metrics["dominant_test_type"],
                "test_type_proof": churn_metrics.get("type_proofs", {}).get(churn_metrics["dominant_test_type"]),
                "test_additions": churn_metrics["test_additions"],
                "test_deletions": churn_metrics["test_deletions"],
                "prod_additions": churn_metrics["prod_additions"],
                "prod_deletions": churn_metrics["prod_deletions"],
                "trial_and_error_commits": pr["total_commits"],
                "resolution_time_seconds": res_time_seconds,
                "independently_fixed_ci": indep_fix,
                
                # Part 2: Project Meta
                "project_stars": pr_meta_map.get(pid, {}).get("stars", 0),
                "project_forks": pr_meta_map.get(pid, {}).get("forks", 0),
            }
            final_results.append(feature_obj)

    print(f"6) Saving {len(final_results)} RQ1 records to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=2)

    print("Success. Payload generated!")

if __name__ == "__main__":
    main()
