"""Pydantic models generated from docs/product-contract.md — single source of truth."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    pothole = "pothole"
    road_damage = "road_damage"
    streetlight = "streetlight"
    water_leak = "water_leak"
    drainage = "drainage"
    flooding = "flooding"
    sanitation = "sanitation"
    fallen_tree = "fallen_tree"
    electrical_hazard = "electrical_hazard"
    obstruction = "obstruction"
    other = "other"


class ServiceOwner(str, Enum):
    ghmc = "GHMC"
    cyberabad = "Cyberabad Municipal Corporation"
    malkajgiri = "Malkajgiri Municipal Corporation"
    water = "Water/Sewerage"
    electricity = "Electricity"
    hydraa = "HYDRAA"
    other = "Other/Review"


class ExtractionResult(BaseModel):
    """AI output: evidence only. Never a severity number."""

    issue_type: IssueType = IssueType.other
    observed: list[str] = Field(default_factory=list)   # facts stated/visible
    claimed: list[str] = Field(default_factory=list)    # unverified citizen claims
    missing: list[str] = Field(default_factory=list)    # important unknowns
    hazards: list[str] = Field(default_factory=list)    # controlled vocab, see prompt
    confidence: float = 0.0                             # 0..1 classification+evidence confidence
    summary: str = ""                                   # one factual line


class DimensionScore(BaseModel):
    score: int = 0          # 0, 1, or 2
    reasons: list[str] = Field(default_factory=list)


class SeverityResult(BaseModel):
    urgency: int = 1        # 1..5
    dimensions: dict[str, DimensionScore] = Field(default_factory=dict)
    overrides: list[str] = Field(default_factory=list)
    review_flag: bool = False
    verification: str = "standard"   # standard | urgent


class TicketOut(BaseModel):
    incident_id: int
    issue_type: IssueType
    service_owner: ServiceOwner
    urgency: int
    confidence: float
    review_flag: bool
    verification: str
    summary: str
    observed: list[str]
    claimed: list[str]
    missing: list[str]
    severity_reasons: dict[str, list[str]]
    duplicate_of: Optional[int] = None
    report_count: int
    context_label: str
    data_source: str        # live | seed
    ai_provider: str        # kimi | mock
