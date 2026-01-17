"""Data models for CMS Medicaid datasets."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContactPoint:
    """Contact information for a dataset."""

    fn: str  # Full name
    email: str

    @classmethod
    def from_dict(cls, data: dict) -> Optional["ContactPoint"]:
        if not data:
            return None
        email = data.get("hasEmail", "")
        if email.startswith("mailto:"):
            email = email[7:]
        return cls(fn=data.get("fn", ""), email=email)


@dataclass
class Publisher:
    """Organization that published a dataset."""

    name: str
    sub_organization_of: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> Optional["Publisher"]:
        if not data:
            return None
        return cls(
            name=data.get("name", ""),
            sub_organization_of=data.get("subOrganizationOf"),
        )


@dataclass
class Distribution:
    """A data file or API endpoint for a dataset."""

    title: str
    description: str
    format: str
    download_url: Optional[str] = None
    access_url: Optional[str] = None
    media_type: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Distribution":
        return cls(
            title=data.get("title", "Untitled"),
            description=data.get("description", ""),
            format=data.get("format", ""),
            download_url=data.get("downloadURL"),
            access_url=data.get("accessURL"),
            media_type=data.get("mediaType"),
        )


@dataclass
class Dataset:
    """Metadata for a CMS Medicaid dataset."""

    identifier: str
    title: str
    description: str
    access_level: str
    modified: str
    keywords: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    distributions: list[Distribution] = field(default_factory=list)
    publisher: Optional[Publisher] = None
    contact_point: Optional[ContactPoint] = None
    issued: Optional[str] = None
    temporal: Optional[str] = None
    spatial: Optional[str] = None
    accrual_periodicity: Optional[str] = None
    license: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Dataset":
        distributions = [
            Distribution.from_dict(d) for d in data.get("distribution", [])
        ]
        return cls(
            identifier=data.get("identifier", ""),
            title=data.get("title", "Untitled"),
            description=data.get("description", ""),
            access_level=data.get("accessLevel", "public"),
            modified=data.get("modified", ""),
            keywords=data.get("keyword", []),
            themes=data.get("theme", []),
            distributions=distributions,
            publisher=Publisher.from_dict(data.get("publisher") or {}),
            contact_point=ContactPoint.from_dict(data.get("contactPoint") or {}),
            issued=data.get("issued"),
            temporal=data.get("temporal"),
            spatial=data.get("spatial"),
            accrual_periodicity=data.get("accrualPeriodicity"),
            license=data.get("license"),
        )

    def matches_search(self, term: str) -> bool:
        """Check if this dataset matches a search term."""
        term_lower = term.lower()
        return (
            term_lower in self.title.lower()
            or term_lower in self.description.lower()
            or any(term_lower in kw.lower() for kw in self.keywords)
            or any(term_lower in th.lower() for th in self.themes)
        )


@dataclass
class Catalog:
    """A collection of datasets from the CMS Medicaid data portal."""

    datasets: list[Dataset] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Catalog":
        datasets = [Dataset.from_dict(d) for d in data.get("dataset", [])]
        return cls(datasets=datasets)

    def search(self, term: str) -> list[Dataset]:
        """Search datasets by keyword."""
        return [d for d in self.datasets if d.matches_search(term)]

    def filter_by_theme(self, theme: str) -> list[Dataset]:
        """Filter datasets by theme/category."""
        theme_lower = theme.lower()
        return [
            d for d in self.datasets if any(theme_lower in t.lower() for t in d.themes)
        ]
