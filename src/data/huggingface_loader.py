"""Module for loading and streaming data from HuggingFace."""

from datasets import load_dataset


class HFDataLoader:
    """Handles streaming and iterative loading from the hao-li/AIDev dataset.

    This class provides an interface to pull specific tables from the Hugging Face
    repository efficiently using streaming or split loading.
    
    Attributes:
        dataset_name (str): The name of the dataset repository on HuggingFace.
    """

    def __init__(self, dataset_name: str = "hao-li/AIDev"):
        """Initializes the HFDataLoader.

        Args:
            dataset_name: The HuggingFace repository name. Defaults to "hao-li/AIDev".
        """
        self.dataset_name = dataset_name

    def load_table(self, table_name: str, split: str = "train", streaming: bool = False):
        """Loads a specific table/configuration from the dataset.

        Args:
            table_name: The name of the configuration/table to load (e.g., 'pull_request').
            split: The dataset split to load. Defaults to 'train'.
            streaming: If True, streams the dataset to save memory. Defaults to False.

        Returns:
            The requested HuggingFace dataset object or iterable stream.
            
        Raises:
            ValueError: If the dataset or table cannot be loaded.
        """
        try:
            return load_dataset(self.dataset_name, table_name, split=split, streaming=streaming)
        except Exception as e:
            raise ValueError(f"Failed to load table '{table_name}' from '{self.dataset_name}': {e}")

