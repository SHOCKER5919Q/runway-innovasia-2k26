"""Integration adapters. Importing the package registers every adapter."""
from app.integrations import adapters as _adapters  # noqa: F401
from app.integrations import pdf_invoice as _pdf  # noqa: F401
from app.integrations.base import PLANNED, REGISTRY, Adapter, NormalisedRow  # noqa: F401
