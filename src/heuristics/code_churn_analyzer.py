"""Module for deep analysis of code churn and test classification ratios."""

import re
from typing import Dict, Any, List


class CodeChurnAnalyzer:
    """Analyzes a PR's file changes to compute test-to-code ratios and test types."""

    # E2E / UI / Browser Tests regex logic
    REGEX_E2E = re.compile(
        r'([/_\-](e2e|cypress|playwright|puppeteer|selenium|webdriver|features|step_definitions|acceptance)[/_\-])|(\.(e2e|cy|spec|feature)\.)',
        re.IGNORECASE
    )

    # Integration Tests regex logic
    REGEX_INTEGRATION = re.compile(
        r'([/_\-](api|db|database|integration|it)[/_\-])|(\.(it|int|integration)\.)',
        re.IGNORECASE
    )

    @classmethod
    def classify_test_type(cls, filepath: str) -> str:
        """Classifies a validated test file into its specific subtype.

        Args:
            filepath: The path of the file to classify.

        Returns:
            A string classification: 'e2e', 'integration', or 'unit'.
        """
        # E2E patterns take highest precedence usually due to specific tool folders
        if cls.REGEX_E2E.search(filepath):
            return 'e2e'
            
        # Integration patterns take middle precedence
        if cls.REGEX_INTEGRATION.search(filepath):
            return 'integration'
            
        # Default fallback for a matched valid test file
        return 'unit'

    @classmethod
    def analyze_pr_churn(cls, commit_files: List[Dict[str, Any]], test_classifier_class) -> Dict[str, Any]:
        """Calculates the aggregate code churn statistics for a given PR's commits.

        Args:
            commit_files: A list of dictionaries representing the 'pr_commit_details' 
                rows belonging to this PR.
            test_classifier_class: The TestFileClassifier class to validate if 
                a file is a valid test file under the AIDev rules.

        Returns:
            A dictionary containing the calculated metrics:
                - prod_additions
                - prod_deletions
                - test_additions
                - test_deletions
                - dominant_test_type
                - type_counts
        """
        metrics = {
            "prod_additions": 0,
            "prod_deletions": 0,
            "test_additions": 0,
            "test_deletions": 0,
            "dominant_test_type": "unknown",
            "type_counts": {
                "unit": 0,
                "integration": 0,
                "e2e": 0
            },
            "type_proofs": {
                "unit": None,
                "integration": None,
                "e2e": None
            }
        }

        # Commits can log the same file multiple times if it is modified across multiple commits
        # So we tally the absolute additions/deletions across all touches in the PR
        for file_row in commit_files:
            # We must ignore deletes and renames as per the paper, only 'added' or 'modified' 
            # are considered valid contributions
            status = (file_row.get("status") or "").lower()
            if status not in ["added", "modified"]:
                continue

            filepath = file_row.get("filename") or ""
            additions = int(file_row.get("additions") or 0)
            deletions = int(file_row.get("deletions") or 0)
            
            # Use our Phase 1 rigorous heuristic classifier to determine if test code
            is_test = test_classifier_class.is_test_file(filepath)

            if is_test:
                metrics["test_additions"] += additions
                metrics["test_deletions"] += deletions
                
                # Further refine the type
                test_type = cls.classify_test_type(filepath)
                metrics["type_counts"][test_type] += 1
                if not metrics["type_proofs"][test_type]:
                    metrics["type_proofs"][test_type] = filepath
            else:
                metrics["prod_additions"] += additions
                metrics["prod_deletions"] += deletions

        # Determine dominant test type based on raw file counts
        max_count = 0
        for t_type, count in metrics["type_counts"].items():
            if count > max_count:
                max_count = count
                metrics["dominant_test_type"] = t_type

        return metrics
