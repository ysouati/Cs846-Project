import json
import os
import sys
import statistics
from typing import List, Dict, Any
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.github_graphql import GitHubGraphQLClient

def calculate_directory_distance(test_path: str, prod_path: str) -> int:
    """Calculates the directory distance between a test and a prod file.
    
    Distance = 0: Same directory
    Distance = 1: One directory apart (e.g. src/a.js vs src/tests/a.test.js)
    Distance = N: N directories apart from their deepest common root.
    """
    parts_test = test_path.split('/')[:-1] # Remove filename
    parts_prod = prod_path.split('/')[:-1] # Remove filename
    
    common_len = 0
    for pt, pp in zip(parts_test, parts_prod):
        if pt == pp:
            common_len += 1
        else:
            break
            
    # Distance is the sum of unique segments from the common root
    dist_test = len(parts_test) - common_len
    dist_prod = len(parts_prod) - common_len
    
    return dist_test + dist_prod

def calculate_pr_locality(test_paths: List[str], prod_paths: List[str]) -> float:
    """Calculates the Median Test Locality Distance for a PR.
    
    For every test file, we find the "closest" production file modified in the same PR,
    then we take the median of those minimum distances.
    """
    if not test_paths or not prod_paths:
        return None
        
    closest_distances = []
    
    for test in test_paths:
        min_distance = float('inf')
        for prod in prod_paths:
            dist = calculate_directory_distance(test, prod)
            if dist < min_distance:
                min_distance = dist
                
        closest_distances.append(min_distance)
        
    return statistics.median(closest_distances) if closest_distances else None

def process_human_dataset(filepath: str) -> List[Dict[str, Any]]:
    print(f"Loading Human data from {filepath}...")
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
        
    output_records = []
    processed = 0
    skipped = 0
    
    for pr in data:
        test_paths = []
        for paths in pr.get("test_type_paths", {}).values():
            test_paths.extend(paths)
        prod_paths = pr.get("prod_paths", [])
        
        if not test_paths or not prod_paths:
            skipped += 1
            continue
            
        median_dist = calculate_pr_locality(test_paths, prod_paths)
        if median_dist is not None:
            output_records.append({
                "pr_id": pr.get("pr_id", pr.get("id")),
                "pr_number": pr.get("pr_number", pr.get("number")),
                "repo_full_name": pr.get("repo_full_name"),
                "author_type": "Human",
                "created_at": pr.get("created_at"),
                "num_test_files": len(test_paths),
                "num_prod_files": len(prod_paths),
                "median_locality_distance": median_dist
            })
            processed += 1
    print(f"   Processed {processed} Human PRs. Skipped {skipped}.")
    return output_records

def process_agent_dataset(filepath: str) -> List[Dict[str, Any]]:
    print(f"\nLoading Agent data from {filepath}...")
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
        
    client = GitHubGraphQLClient()
    
    repo_to_prs = defaultdict(list)
    for pr in data:
        repo_name = pr.get("repo_full_name")
        if repo_name:
            repo_to_prs[repo_name].append(pr)
            
    output_records = []
    processed = 0
    skipped = 0
    
    total_repos = len(repo_to_prs)
    for i, (repo_full_name, pr_list) in enumerate(repo_to_prs.items()):
        try:
            owner, name = repo_full_name.split("/")
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
            skipped += len(pr_list)
            continue
            
        for pr in pr_list:
            test_paths = []
            for paths in pr.get("test_type_paths", {}).values():
                test_paths.extend(paths)
            
            # Subtractive logic for prod paths. Whatever wasn't verified as a test path is prod.
            test_set = set(test_paths)
            files_changed = file_map.get(pr["pr_number"], [])
            prod_paths = [p for p in files_changed if p not in test_set]
            
            if not test_paths or not prod_paths:
                skipped += 1
                continue
                
            median_dist = calculate_pr_locality(test_paths, prod_paths)
            if median_dist is not None:
                output_records.append({
                    "pr_id": pr.get("pr_id"),
                    "pr_number": pr.get("pr_number"),
                    "repo_full_name": pr.get("repo_full_name"),
                    "author_type": "Agent",
                    "created_at": pr.get("created_at"),
                    "num_test_files": len(test_paths),
                    "num_prod_files": len(prod_paths),
                    "median_locality_distance": median_dist
                })
                processed += 1
                
    print(f"   Processed {processed} Agent PRs. Skipped {skipped}.")
    return output_records

def main():
    print("--- RQ3 Locality Feature Extraction ---")
    human_records = process_human_dataset("rq3_human_deepseek_filtered.json")
    agent_records = process_agent_dataset("rq1_deepseek_filtered.json")
    
    combined_dataset = agent_records + human_records
    print(f"\nFinal Combined RQ3 Dataset: {len(combined_dataset)} comparable PRs.")
    
    with open("rq3_locality_dataset.json", "w") as f:
        json.dump(combined_dataset, f, indent=2)
        
    print("Exported calculated locality metrics to rq3_locality_dataset.json")

if __name__ == "__main__":
    main()
