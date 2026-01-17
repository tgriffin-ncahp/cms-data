"""CMS Medicaid Data Browser - Browse and query CMS Medicaid datasets.

Example usage:
    >>> from cms_data import CmsMedicaidClient
    >>> client = CmsMedicaidClient()
    >>> catalog = client.fetch_catalog()
    >>> for ds in catalog.datasets[:5]:
    ...     print(ds.title)
"""

from .api import CmsMedicaidClient
from .models import Catalog, ContactPoint, Dataset, Distribution, Publisher

__all__ = [
    "CmsMedicaidClient",
    "Catalog",
    "Dataset",
    "Distribution",
    "Publisher",
    "ContactPoint",
]

__version__ = "0.1.0"
