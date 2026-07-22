"""Evidence-backed rolling life-insurance market research."""

from .repository import MarketAnalysisRepository
from .validator import ReportValidationError, validate_report

__all__ = ["MarketAnalysisRepository", "ReportValidationError", "validate_report"]
