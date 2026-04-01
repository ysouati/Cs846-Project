import json
import os
import sys
from collections import defaultdict

# Add the root directory to sys.path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data.github_graphql import GitHubGraphQLClient

def main():
    print("1) Loading rq1_deepseek_filtered.json...")
    with open("rq1_deepseek_filtered.json", "r") as f:
        filtered_prs = json.load(f)
        
    print("2) Loading modular_filtered_test_prs.json to retrieve commit pipelines...")
    with open("modular_filtered_test_prs.json", "r") as f:
        raw_prs = json.load(f)
        
    # Map PR ID to its raw commit pipeline
    raw_pr_map = {str(pr["pr_id"]): pr.get("commits", []) for pr in raw_prs}
    
    graphql_client = GitHubGraphQLClient()
    
    repo_grouped_prs = defaultdict(list)
    for pr in filtered_prs:
        if "ci_had_failure" in pr:
            continue
        
        pid = str(pr["pr_id"])
        commits = raw_pr_map.get(pid, [])
        if commits:
            repo_grouped_prs[pr["repo_full_name"]].append((pr, commits))
            
    total_repos = len(repo_grouped_prs)
    if total_repos == 0:
        print("All PRs already have 'ci_had_failure' augmented. Exiting.")
        return
        
    print(f"3) Querying GraphQL for {total_repos} repositories...")
    
    repo_counter = 0
    save_counter = 0
    
    for repo_fn, pr_tuples in repo_grouped_prs.items():
        repo_counter += 1
        print(f"   [{repo_counter}/{total_repos}] Analyzing {repo_fn} ({len(pr_tuples)} PRs)...")
        
        # Collect all unique commits needed for this repo
        repo_commit_shas = set()
        for _, commits in pr_tuples:
            for commit in commits:
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
        
        for pr, commits in pr_tuples:
            had_failure = False
            for commit in commits:
                sha = commit.get("sha")
                state = commit_statuses.get(sha, "NONE")
                if state in ("FAILURE", "ERROR"):
                    had_failure = True
                    break # We only need to know if it EVER failed
                    
            pr["ci_had_failure"] = had_failure
            
        save_counter += 1
        # Save progress every 20 repos so we don't lose data if it crashes
        if save_counter % 20 == 0:
            with open("rq1_deepseek_filtered.json", "w") as f:
                json.dump(filtered_prs, f, indent=2)
                
    # Final save
    print("4) Saving augmented dataset to rq1_deepseek_filtered.json...")
    with open("rq1_deepseek_filtered.json", "w") as f:
        json.dump(filtered_prs, f, indent=2)
        
    print("Success. Dataset augmented with ci_had_failure boolean.")

if __name__ == "__main__":
    main()
