"""Main pipeline executing the identification of AIDev-pop Test Pull Requests.

This module coordinates loading raw data from HuggingFace, executing test heuristics 
on commit diffs, and formatting identified Test PRs into a clean JSON structure 
downstream.
"""

import json
import argparse
from typing import Any, Dict, List
from collections import defaultdict

from src.data.huggingface_loader import HFDataLoader
from src.data.github_graphql import GitHubGraphQLClient
from src.heuristics.test_classifier import TestFileClassifier


def process_pull_requests(loader: HFDataLoader, limit: int = 0) -> List[Dict[str, Any]]:
    """Processes datasets to identify Test Pull Requests.

    This function loops through the PR commits and checks for valid test file additions 
    or modifications, excluding auto-generated merge commits. It does not fetch 
    timestamps from the GitHub API. It assumes the 'pull_request' table is already 
    the AIDev-pop (<100 stars) dataset.

    Args:
        loader: An instantiated HFDataLoader object to pull tables.
        limit: If strictly greater than 0, stops processing after finding `limit` 
            number of valid Test PRs. Defaults to 0 (process all).

    Returns:
        A list of dictionaries. Each dictionary represents a mapped Test PR 
        containing PR metadata and a list of identified test/prod file changes.
    """
    print("1) Discovering PRs in the AIDev-pop dataset format...")
    ds_pr = loader.load_table("pull_request")
    
    pop_prs = {}
    for pr in ds_pr:
        pr_id = str(pr.get('id'))
        if pr_id != "None":
            pop_prs[pr_id] = pr
            
    print(f"   Found {len(pop_prs)} pull requests.")

    print("2) Scanning PR Commit Details for Test File Changes...")
    ds_commit_details = loader.load_table("pr_commit_details")
    
    test_prs = set()
    pr_commit_map = defaultdict(list)
    
    for commit in ds_commit_details:
        pr_id = str(commit.get('pr_id'))
        if pr_id not in pop_prs:
            continue
            
        msg = commit.get('message') or ''
        
        # Papers explicitly states to exclude merge commits
        if msg.lower().startswith('merge'):
            continue 
            
        pr_commit_map[pr_id].append(commit)
        
        status = str(commit.get('status', '')).lower()
        filename = commit.get('filename') or ''
        
        # Touches is defined as 'added' or 'modified'
        if status in ('added', 'modified'):
            if TestFileClassifier.is_test_file(filename):
                test_prs.add(pr_id)
                
    test_pr_list = list(test_prs)
    print(f"   Identified {len(test_pr_list)} valid Test PRs.")
    
    if limit > 0:
        test_pr_list = test_pr_list[:limit]
        print(f"   Limiting output to {limit} Test PRs.")

    print("3) Formatting Output Data...")
    
    # Needs repository name mapping
    ds_repo = loader.load_table("repository")
    repo_names = {}
    for repo in ds_repo:
        repo_names[str(repo.get('id'))] = repo.get('full_name')

    # Group valid Test PRs by repo_full_name so we can batch query GraphQL efficiently
    repo_grouped_prs = defaultdict(list)
    results = []
    
    for pr_id in test_pr_list:
        pr_data = pop_prs[pr_id]
        repo_id = str(pr_data.get('repo_id'))
        repo_full_name = repo_names.get(repo_id, "Unknown")
        repo_grouped_prs[repo_full_name].append(pr_id)
        
    # GraphQL Fetching execution
    graphql_client = GitHubGraphQLClient()
    total_repos = len(repo_grouped_prs)
    print(f"4) Fetching Commit Timestamps via GraphQL for {total_repos} repositories...")
    
    repo_counter = 0
    for repo_full_name, pr_ids in repo_grouped_prs.items():
        repo_counter += 1
        print(f"   [{repo_counter}/{total_repos}] Fetching timelines for {repo_full_name} ({len(pr_ids)} PRs)...")
        
        try:
            owner, name = repo_full_name.split('/')
            pr_numbers_in_repo = [int(pop_prs[pr_id].get('number', 0)) for pr_id in pr_ids]
            
            # This batch fetches all timelines for this repo's PRs natively
            repo_timelines = graphql_client.fetch_pr_commits_batch(owner, name, pr_numbers_in_repo)
            
            # Mold the timelines into the final output JSON list
            for pr_id in pr_ids:
                pr_data = pop_prs[pr_id]
                pr_number = int(pr_data.get('number', 0))
                
                # Fetch the chronological commits we just got from GraphQL
                commits_timeline = repo_timelines.get(pr_number, [])
                
                results.append({
                    "pr_id": int(pr_id),
                    "pr_number": pr_number,
                    "repo_full_name": repo_full_name,
                    "agent_type": pr_data.get('agent'),
                    "merged_at": pr_data.get('merged_at'),
                    "created_at": pr_data.get('created_at'),
                    "total_commits": len(commits_timeline),
                    "commits": commits_timeline
                })
        except Exception as e:
            print(f"   Error fetching {repo_full_name}: {e}")
            # Insert graceful fallback without timestamps if GraphQL fatally errors on an edge repo
            for pr_id in pr_ids:
                pr_data = pop_prs[pr_id]
                results.append({
                    "pr_id": int(pr_id),
                    "pr_number": int(pr_data.get('number', 0)),
                    "repo_full_name": repo_full_name,
                    "agent_type": pr_data.get('agent'),
                    "merged_at": pr_data.get('merged_at'),
                    "created_at": pr_data.get('created_at'),
                    "total_commits": 0,
                    "commits": []
                })

    return results


def main():
    """CLI Entry point for extracting Test Pull Requests."""
    parser = argparse.ArgumentParser(description='Extract and filter AIDev Test PRs.')
    parser.add_argument('--limit', type=int, default=0, 
                        help='Limit the number of Test PRs extracted. 0 means no limit.')
    parser.add_argument('--output', type=str, default='modular_filtered_test_prs.json',
                        help='Destination path for the output JSON.')
    args = parser.parse_args()

    loader = HFDataLoader(dataset_name="hao-li/AIDev")
    filtered_prs = process_pull_requests(loader, limit=args.limit)

    print(f"5) Saving {len(filtered_prs)} records to {args.output}...")
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(filtered_prs, f, indent=2)


if __name__ == "__main__":
    main()
