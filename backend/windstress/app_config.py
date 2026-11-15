
import os

# NASA data configuration
MAX_GRANULES = 1500
MAX_PRODUCTS = 3
MAX_WORKERS = 4
HTTP_TIMEOUT = 120

CMR_URL = "https://cmr.earthdata.nasa.gov/search"

GIOVANNI_TIMESERIES_URL = (
    "https://api.giovanni.earthdata.nasa.gov/timeseries"
)

SCIENCE_TOPICS = ("ATMOSPHERE", "OCEANS")

TRUSTED_AUTH_SUFFIXES = (
    ".nasa.gov",
    ".nsidc.org",
)

# Anthropic configuration
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def providers():
    raw = os.environ.get("CMR_PROVIDERS", "GES_DISC")
    return [
        p.strip()
        for p in raw.split(",")
        if p.strip()
    ]


def claude_model():
    return os.environ.get(
        "CLAUDE_MODEL",
        "claude-sonnet-5-5"
    )


def env(name, default=None):
    return os.environ.get(name, default)
