"""Dataset discovery profiles and constants for CMS data updates."""

import re

# Maps dataset types to their catalog search patterns and loader behavior.
# Used by the `update` command to discover the latest datasets.
DATASET_PROFILES = {
    "sdu": {
        "search_term": "State Drug Utilization Data",
        "title_pattern": re.compile(r"State Drug Utilization Data\s+(\d{4})", re.IGNORECASE),
        "loader_type": "sdu",
        "file_prefix": "sdud",
        "table_prefix": "sdu",
    },
    "nadac": {
        "search_term": "NADAC (National Average Drug Acquisition Cost)",
        "title_pattern": re.compile(r"NADAC\b.*", re.IGNORECASE),
        "loader_type": "nadac",
        "file_prefix": "nadac",
        "table_prefix": "nadac",
    },
    "nadac_comparison": {
        "search_term": "NADAC Comparison",
        "title_pattern": re.compile(r"NADAC Comparison", re.IGNORECASE),
        "loader_type": "nadac",
        "file_prefix": "nadac_comparison",
        "table_prefix": "nadac_comparison",
    },
}

DEFAULT_STATE_FILTER = "NC"
