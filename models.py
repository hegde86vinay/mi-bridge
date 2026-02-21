from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RawAlert(BaseModel):
    incident_id: str
    source: Literal["dynatrace", "splunk", "kibana"]
    severity: Literal["P1", "P2", "P3", "P4"]
    title: str
    affected_services: list[str]
    environment: str
    timestamp: datetime
    error_rate: float
    raw_payload: dict[str, Any]


class ImpactAnalysisOutput(BaseModel):
    blast_radius: list[str]
    customer_segments_affected: list[str]
    estimated_users_impacted: int
    revenue_impact_per_minute: str
    severity_recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SimilarIncident(BaseModel):
    incident_id: str
    title: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    root_cause: str
    resolution: str
    resolution_time_minutes: int


class SimilarIncidentOutput(BaseModel):
    incidents: list[SimilarIncident]
    top_match: SimilarIncident
    suggested_runbook: str
    reasoning: str


class MISummaryOutput(BaseModel):
    headline: str
    narrative: str
    timeline: list[dict[str, Any]]
    teams_to_engage: list[dict[str, Any]]
    next_steps: list[str]


class RCAOutput(BaseModel):
    probable_root_causes: list[dict[str, Any]]
    correlated_change_requests: list[dict[str, Any]]
    recommended_resolution: str
    rollback_candidate: str | None
    remediation_steps: list[str]
    evidence_trail: list[dict[str, Any]]


class IncidentContext(BaseModel):
    incident_id: str
    alert: RawAlert
    impact_analysis: ImpactAnalysisOutput | None = None
    similar_incidents: SimilarIncidentOutput | None = None
    mi_summary: MISummaryOutput | None = None
    rca: RCAOutput | None = None
    phase_timings: dict[str, float] = Field(default_factory=dict)
    created_at: datetime
    # Captured log entries for web dashboard — each dict has {timestamp, agent, message, phase}
    log_entries: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
