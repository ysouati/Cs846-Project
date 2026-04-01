import json
import os
import sys
from collections import defaultdict
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from heuristics.test_classifier import TestFileClassifier
from heuristics.code_churn_analyzer import CodeChurnAnalyzer
from data.github_graphql import GitHubGraphQLClient

def main():
    print("1) Loading Agent Target Domains (Repositories)...")
    try:
        with open("rq1_deepseek_filtered.json", "r") as f:
            agent_data = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find rq1_deepseek_filtered.json")
        return

    # Extract all distinct repository names the Agent acted in
    target_repos = {pr["repo_full_name"] for pr in agent_data if pr.get("repo_full_name")}
    print(f"   Identified {len(target_repos)} unique Repositories to sample Human PRs from.")

    print("2) Streaming Human Pull Requests from HuggingFace...")
    # Load human PRs
    human_prs = load_dataset("hao-li/AIDev", "human_pull_request", split="train", streaming=True)
    
    # Group PRs by repo to prepare for GraphQL batching
    repo_to_prs = defaultdict(list)
    total_candidate_prs = 0
    
    print("   Isolating Human PRs in target domains...")
    for pr in human_prs:
        repo_url = pr.get("repo_url", "")
        # Parse the repo full name from URL
        repo_name = "/".join(repo_url.split("/")[-2:])
        
        if repo_name in target_repos:
            repo_to_prs[repo_name].append({
                "pr_id": pr["id"],
                "pr_number": pr["number"],
                "repo_full_name": repo_name,
                "title": pr.get("title", ""),
                "body": pr.get("body", ""),
                "user": pr.get("user", "Human"),
                "merged_at": pr.get("merged_at"),
                "state": pr.get("state", ""),
                "html_url": pr.get("html_url", ""),
                "test_type_paths": defaultdict(list),
                "prod_paths": []
            })
            total_candidate_prs += 1
            if total_candidate_prs >= 5000:
                print("   [Reached 5000 candidate cutoff buffer to prevent GraphQL overload]")
                break
                
    print(f"   Collected {total_candidate_prs} Human PRs connected to our target repos.")
    
    if total_candidate_prs == 0:
        print("Error: No human PRs found matching the Agent repositories.")
        return
        
    print("3) Querying GitHub GraphQL for PR File Changes...")
    client = GitHubGraphQLClient()
    classifier = TestFileClassifier()
    
    valid_test_prs = []
    matched_test_files = 0
    
    total_repos = len(repo_to_prs)
    for i, (repo_full_name, pr_list) in enumerate(repo_to_prs.items()):
        try:
            owner, name = repo_full_name.split("/")
            
            # Additional cleanup for hidden or deleted repos throwing 404s
            if not owner or not name:
                continue
        except ValueError:
            continue
            
        pr_numbers = [pr["pr_number"] for pr in pr_list]
        print(f"   ({i+1}/{total_repos}) Fetching {len(pr_numbers)} PR files for {repo_full_name} via GraphQL...")
        
        try:
            file_map = client.fetch_pr_files_batch(owner, name, pr_numbers)
        except Exception as e:
            print(f"   [!] Failed to fetch {repo_full_name}: {e}")
            continue
        
        for pr in pr_list:
            files_changed = file_map.get(pr["pr_number"], [])
            has_test = False
            
            for path in files_changed:
                if classifier.is_test_file(path):
                    test_type = CodeChurnAnalyzer.classify_test_type(path)
                    pr["test_type_paths"][test_type].append(path)
                    has_test = True
                    matched_test_files += 1
                else:
                    pr["prod_paths"].append(path)
                    
            if has_test:
                valid_test_prs.append(pr)

    print(f"\n4) Final Extraction Complete: {len(valid_test_prs)} Human PRs passed the Test-Regex heuristic Filter.")
    print(f"   Total Test Files localized for DeepSeek evaluation: {matched_test_files}")
    
    # Format and save
    with open("rq3_human_regex_prs.json", "w") as f:
        json.dump(valid_test_prs, f, indent=2)
        
    print("Exported payload to rq3_human_regex_prs.json.")

if __name__ == "__main__":
    main()
