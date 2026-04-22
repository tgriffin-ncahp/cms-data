"""CMS Medicaid Data Browser - Browse and query CMS Medicaid datasets.

Example usage:
    >>> from cms_data import CmsMedicaidClient
    >>> client = CmsMedicaidClient()
    >>> catalog = client.fetch_catalog()
    >>> for ds in catalog.datasets[:5]:
    ...     print(ds.title)
"""

from .api import CmsMedicaidClient
from .loader import create_indexes, load_nadac, load_sdu, make_engine
from .models import Catalog, ContactPoint, Dataset, Distribution, Publisher

__all__ = [
    "CmsMedicaidClient",
    "Catalog",
    "Dataset",
    "Distribution",
    "Publisher",
    "ContactPoint",
    "load_sdu",
    "load_nadac",
    "create_indexes",
    "make_engine",
]

__version__ = "0.1.0"
