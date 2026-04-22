"""API client for CMS Medicaid data portal."""

import json
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

from .models import Catalog, Dataset, Distribution

BASE_URL = "https://data.medicaid.gov"
CATALOG_URL = f"{BASE_URL}/data.json"
DATASTORE_URL = f"{BASE_URL}/api/1/datastore/query"

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "cms-data"


class CmsMedicaidClient:
    """Client for browsing and querying CMS Medicaid data.

    Example usage:
        >>> client = CmsMedicaidClient()
        >>> catalog = client.fetch_catalog()
        >>> for ds in catalog.datasets[:5]:
        ...     print(ds.title)

        >>> df = client.query("ce4cf49b-a21b-5a53-bbc3-509414940847", limit=10)
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_dir: Optional[Path] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.timeout = timeout
        self._catalog: Optional[Catalog] = None
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def fetch_catalog(self, force_refresh: bool = False) -> Catalog:
        """Fetch the full dataset catalog from data.medicaid.gov.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Catalog object containing all datasets.
        """
        if self._catalog and not force_refresh:
            return self._catalog

        cache_file = self.cache_dir / "catalog.json"

        if cache_file.exists() and not force_refresh:
            try:
                data = json.loads(cache_file.read_text())
                self._catalog = Catalog.from_dict(data)
                return self._catalog
            except (json.JSONDecodeError, KeyError):
                pass

        response = self._client.get(f"{self.base_url}/data.json")
        response.raise_for_status()
        data = response.json()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data))

        self._catalog = Catalog.from_dict(data)
        return self._catalog

    def search(self, term: str, theme: Optional[str] = None) -> list[Dataset]:
        """Search datasets by keyword and optionally filter by theme.

        Args:
            term: Search term to match against title, description, keywords.
            theme: Optional theme/category to filter by.

        Returns:
            List of matching datasets.
        """
        catalog = self.fetch_catalog()
        results = catalog.search(term)

        if theme:
            results = [
                d
                for d in results
                if any(theme.lower() in t.lower() for t in d.themes)
            ]

        return results

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a single dataset by its identifier.

        Args:
            dataset_id: The dataset UUID or identifier.

        Returns:
            Dataset object or None if not found.
        """
        catalog = self.fetch_catalog()
        for dataset in catalog.datasets:
            if dataset.identifier == dataset_id:
                return dataset
        return None

    def get_distributions(self, dataset_id: str) -> list[Distribution]:
        """Get all distributions (data files) for a dataset.

        Args:
            dataset_id: The dataset UUID or identifier.

        Returns:
            List of Distribution objects.
        """
        dataset = self.get_dataset(dataset_id)
        if dataset:
            return dataset.distributions
        return []

    def query(
        self,
        dataset_id: str,
        limit: int = 100,
        offset: int = 0,
        conditions: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Query data from a dataset using the DKAN datastore API.

        Args:
            dataset_id: The dataset UUID.
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            conditions: Optional filter conditions.

        Returns:
            pandas DataFrame with query results.
        """
        url = f"{self.base_url}/api/1/datastore/query/{dataset_id}/0"
        params: dict[str, str | int] = {"limit": limit, "offset": offset}

        if conditions:
            params["conditions"] = json.dumps(conditions)

        response = self._client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results)

    def download(
        self,
        url: str,
        output_path: Optional[Path] = None,
        show_progress: bool = True,
    ) -> Path:
        """Download a distribution file.

        Args:
            url: URL of the file to download.
            output_path: Where to save the file. If None, saves to current directory.
            show_progress: Whether to show download progress.

        Returns:
            Path to the downloaded file.
        """
        if output_path is None:
            filename = url.split("/")[-1].split("?")[0]
            output_path = Path.cwd() / filename

        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))

            with open(output_path, "wb") as f:
                downloaded = 0
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if show_progress and total:
                        pct = (downloaded / total) * 100
                        print(f"\rDownloading: {pct:.1f}%", end="", flush=True)

        if show_progress:
            print()

        return output_path

    def download_with_progress(
        self,
        url: str,
        output_path: Path,
        progress,
        task_id,
    ) -> Path:
        """Download a file with rich progress bar integration.

        Args:
            url: URL of the file to download.
            output_path: Where to save the file.
            progress: A rich.progress.Progress instance.
            task_id: The rich progress task ID to update.

        Returns:
            Path to the downloaded file.
        """
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            progress.update(task_id, total=total or None)

            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

        return output_path

    def list_themes(self) -> list[str]:
        """Get all unique themes/categories across datasets.

        Returns:
            Sorted list of unique themes.
        """
        catalog = self.fetch_catalog()
        themes = set()
        for dataset in catalog.datasets:
            themes.update(dataset.themes)
        return sorted(themes)

    def list_keywords(self) -> list[str]:
        """Get all unique keywords across datasets.

        Returns:
            Sorted list of unique keywords.
        """
        catalog = self.fetch_catalog()
        keywords = set()
        for dataset in catalog.datasets:
            keywords.update(dataset.keywords)
        return sorted(keywords)
