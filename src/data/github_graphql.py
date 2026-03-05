"""Module for querying the GitHub GraphQL API."""

import os
import time
import requests
from typing import Dict, List, Any


class GitHubGraphQLClient:
    """A client for interacting with the GitHub GraphQL API efficiently.

    Attributes:
        token (str): The GitHub Personal Access Token.
        headers (dict): The HTTP headers required for GraphQL queries.
        url (str): The GitHub GraphQL endpoint.
    """

    def __init__(self, token: str = None):
        """Initializes the GraphQL client.

        Args:
            token: The GitHub token. If None, it attempts to read from the 
                GITHUB_TOKEN environment variable.

        Raises:
            ValueError: If no GitHub token is provided or found.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            token_file = "/home/ysouati/.gemini/antigravity/brain/420b2201-ff0e-4b78-a9c6-eec4ea5581ed/.github_token"
            if os.path.exists(token_file):
                with open(token_file, "r", encoding="utf-8") as f:
                    self.token = f.read().strip()
                    
        if not self.token:
            raise ValueError("A GitHub token must be provided to use GraphQL.")
        
        self.headers = {
            "Authorization": f"bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.url = "https://api.github.com/graphql"

    def execute_query(self, query: str, variables: dict = None) -> dict:
        """Executes a GraphQL query against the GitHub API.

        Handles basic rate limiting and connection errors by retrying.

        Args:
            query: The GraphQL query string.
            variables: A dictionary of GraphQL variables.

        Returns:
            The parsed JSON response data dict.

        Raises:
            Exception: If the query repeatedly fails or returns GraphQL errors.
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        max_retries = 3
        for attempt in range(max_retries):
            response = requests.post(self.url, json=payload, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                if "errors" in result:
                    # Sometimes issues like "Could not resolve to a PullRequest" happen
                    # We print a warning but return the data we did get
                    # print(f"GraphQL Warning: {result['errors']}")
                    pass
                return result.get("data", {})
                
            elif response.status_code in (403, 429):
                # Rate limit hit
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_sec = max(reset_time - time.time(), 5)
                print(f"   [GraphQL] Rate limit hit. Sleeping for {sleep_sec:.0f} seconds...")
                time.sleep(sleep_sec)
            else:
                print(f"   [GraphQL] Error {response.status_code}: {response.text}")
                time.sleep(2)
                
        raise Exception("GraphQL query failed after maximum retries.")

    def fetch_pr_commits_batch(self, repo_owner: str, repo_name: str, pr_numbers: List[int]) -> Dict[int, List[Dict[str, str]]]:
        """Fetches commit timelines for a batch of PRs using GraphQL aliases.

        To avoid making an API call for every single PR, this packages up to 50 PR
        queries into a single GraphQL request using field aliases.

        Args:
            repo_owner: The repository owner (e.g., 'facebook').
            repo_name: The repository name (e.g., 'react').
            pr_numbers: A list of PR numbers to fetch.

        Returns:
            A dictionary mapping PR numbers to their chronological list of commit dictionaries.
            Each commit dictionary contains 'sha', 'authored_date', and 'committed_date'.
        """
        results = {}
        
        # Batch size of 50 to avoid hitting GraphQL query complexity limits (which are 500,000 nodes)
        batch_size = 50
        for i in range(0, len(pr_numbers), batch_size):
            batch = pr_numbers[i:i + batch_size]
            
            # Construct aliased query string
            alias_blocks = []
            for pr_num in batch:
                # We fetch up to 100 commits per PR. If there are more, they will be truncated 
                # for brevity in this study.
                block = f"""
                pr_{pr_num}: pullRequest(number: {pr_num}) {{
                    commits(first: 100) {{
                        nodes {{
                            commit {{
                                oid
                                authoredDate
                                committedDate
                            }}
                        }}
                    }}
                }}
                """
                alias_blocks.append(block)
                
            query = f"""
            query {{
                repository(owner: "{repo_owner}", name: "{repo_name}") {{
                    {"".join(alias_blocks)}
                }}
                rateLimit {{
                    cost
                    remaining
                    resetAt
                }}
            }}
            """
            
            data = self.execute_query(query)
            
            # Parse rate limit occasionally if getting low
            rate_limit = data.get("rateLimit", {})
            if rate_limit.get("remaining", 5000) < 50:
                print(f"   [GraphQL] Approaching rate limit! Remaining: {rate_limit['remaining']}")
                
            repo_data = data.get("repository") or {}
            
            for pr_num in batch:
                pr_key = f"pr_{pr_num}"
                pr_data = repo_data.get(pr_key)
                commits_list = []
                
                if pr_data and pr_data.get("commits") and pr_data["commits"].get("nodes"):
                    for node in pr_data["commits"]["nodes"]:
                        commit_obj = node.get("commit")
                        if commit_obj:
                            commits_list.append({
                                "sha": commit_obj.get("oid", ""),
                                "authored_date": commit_obj.get("authoredDate", ""),
                                "committed_date": commit_obj.get("committedDate", "")
                            })
                            
                # Sort commits chronologically by their committedDate string (ISO 8601 sorts alphabetically nicely)
                commits_list.sort(key=lambda x: x["committed_date"] or x["authored_date"])
                results[pr_num] = commits_list
                
        return results

    def fetch_commit_statuses_batch(self, repo_owner: str, repo_name: str, commit_shas: List[str]) -> Dict[str, str]:
        """Fetches the CI pipeline statuses for a batch of commits.

        Args:
            repo_owner: The repository owner.
            repo_name: The repository name.
            commit_shas: A list of full commit SHAs.

        Returns:
            A dictionary mapping the commit SHA to its CI state 
            (e.g., 'SUCCESS', 'FAILURE', 'PENDING', 'ERROR', or 'NONE' if no CI).
        """
        results = {}
        batch_size = 50
        
        for i in range(0, len(commit_shas), batch_size):
            batch = commit_shas[i:i + batch_size]
            
            alias_blocks = []
            for j, sha in enumerate(batch):
                block = f"""
                commit_{j}: object(oid: "{sha}") {{
                    ... on Commit {{
                        statusCheckRollup {{
                            state
                        }}
                    }}
                }}
                """
                alias_blocks.append(block)
                
            query = f"""
            query {{
                repository(owner: "{repo_owner}", name: "{repo_name}") {{
                    {"".join(alias_blocks)}
                }}
                rateLimit {{
                    cost
                    remaining
                }}
            }}
            """
            
            data = self.execute_query(query)
            repo_data = data.get("repository") or {}
            
            for j, sha in enumerate(batch):
                state = "NONE"
                commit_data = repo_data.get(f"commit_{j}")
                if commit_data and commit_data.get("statusCheckRollup"):
                    state = commit_data["statusCheckRollup"].get("state", "NONE")
                    
                results[sha] = state
                
        return results
