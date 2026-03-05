"""Module containing heuristic algorithms to identify testing artifacts."""

import os
import re


class TestFileClassifier:
    """Classifies files as test-related based on path and name heuristics.

    Utilizes exact regex methodologies derived from literature to flag 
    testing files, while safely ignoring non-executable or documentation extensions.
    
    Attributes:
        regex_name (re.Pattern): Matches common test directory/file names.
        regex_token (re.Pattern): Matches files containing 'test' or 'spec' as standalone tokens.
        regex_suffix (re.Pattern): Matches files ending with 'Test' or 'Spec'.
        excluded_extensions (set): File extensions strictly excluded from matching.
    """

    EXCLUDED_EXTENSIONS = {
        ".csv", ".doc", ".json", ".md", ".mk", ".rtf", ".txt", ".yaml", ".yml"
    }

    # Name: Path contains a file/directory named test, tests, testing, or cypress
    REGEX_NAME = re.compile(
        r"(?:^|[\\/])(?:tests?|testing|cypress)(?:[\\/]?$|/)", 
        re.IGNORECASE
    )
    
    # Token: Name includes test or spec as a token delimited by \/_.-
    REGEX_TOKEN = re.compile(
        r"(?:^|[\\/_.-])(?:test|spec)(?:[\\/_.-]?$)", 
        re.IGNORECASE
    )
    
    # Suffix: Directory or file name contains Test or Spec as a suffix
    REGEX_SUFFIX = re.compile(
        r"(?:Test|Spec)(?:$|\.)"
    )

    @classmethod
    def is_test_file(cls, filepath: str) -> bool:
        """Determines if a given file path points to a test file.

        Args:
            filepath: The relative or absolute path of the file to evaluate.

        Returns:
            True if the file matches testing heuristic patterns and is not 
            an excluded type; False otherwise.
        """
        if not filepath:
            return False

        ext = os.path.splitext(filepath)[1].lower()
        if ext in cls.EXCLUDED_EXTENSIONS:
            return False

        return bool(
            cls.REGEX_NAME.search(filepath) or 
            cls.REGEX_TOKEN.search(filepath) or 
            cls.REGEX_SUFFIX.search(filepath)
        )
