from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiagnosticStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    INFO = "INFO"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    ELEVATED = "ELEVATED"


class RemediationAction(BaseModel):
    id: str
    description: str
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_admin: bool = False


class DiagnosticResult(BaseModel):
    probe_id: str
    category: str
    status: DiagnosticStatus
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    remediations: List[RemediationAction] = Field(default_factory=list)
    knowledge_refs: List[str] = Field(default_factory=list)


class DiagnosticReport(BaseModel):
    timestamp: str
    total_probes: int
    pass_count: int
    warn_count: int
    fail_count: int
    results: List[DiagnosticResult] = Field(default_factory=list)
