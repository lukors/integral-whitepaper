### Formal FRS Specification: Pseudocode + Math Sketches

High-Level Types: These are shared data structures used across FRS modules (Python-style pseudocode; illustrative).

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime

# ============================================================
# Shared Enumerations / Labels
# ============================================================

FRSModuleId = Literal["FRS-1", "FRS-2", "FRS-3", "FRS-4", "FRS-5", "FRS-6", "FRS-7"]

SignalSource = Literal[
    "COS",
    "OAD",
    "ITC",
    "CDS",
    "ECO",        # external ecological monitoring
    "FED",        # inter-node / federated exchanges
]

SignalDomain = Literal[
    "ecology",
    "materials",
    "energy",
    "labor",
    "throughput",
    "quality_reliability",
    "distribution_access",
    "dependency_autonomy",
    "governance_participation",
    "ethics_proto_market",
    "security_integrity",
    "other",
]

Severity = Literal["info", "low", "moderate", "high", "critical"]
Scope = Literal["local", "node", "regional", "federation"]
Persistence = Literal["transient", "emerging", "persistent", "structural"]
Confidence = Literal["low", "medium", "high"]


# ============================================================
# Base Signal Primitives (used in FRS-1)
# ============================================================

@dataclass
class Metric:
    """
    A single quantitative measurement or computed indicator.
    """
    name: str
    value: float
    unit: str
    quality: float = 1.0                              # 0–1 confidence in data quality
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticTag:
    """
    A semantic label used for cross-system normalization and routing.
    """
    key: str
    value: str
    weight: float = 1.0


@dataclass
class SignalEnvelope:
    """
    Canonical container for any incoming signal FRS can ingest.
    This is the unit of 'perception' in FRS-1.
    """
    id: str
    source: SignalSource
    domain: SignalDomain

    node_id: str
    federation_id: Optional[str]
    created_at: datetime
    observed_at: Optional[datetime] = None           # when phenomenon occurred (if different)

    tags: List[SemanticTag] = field(default_factory=list)
    metrics: List[Metric] = field(default_factory=list)
    notes: str = ""

    schema_version: str = "v1"
    upstream_ref_ids: Dict[str, str] = field(default_factory=dict)  # {"cos_plan_id": "...", ...}
    prev_hash: Optional[str] = None
    entry_hash: Optional[str] = None


@dataclass
class SignalPacket:
    """
    FRS-1 output: a normalized, time-aligned bundle of SignalEnvelopes
    representing system state over a window.
    """
    id: str
    node_id: str
    time_window_start: datetime
    time_window_end: datetime

    envelopes: List[SignalEnvelope] = field(default_factory=list)

    domains_present: List[SignalDomain] = field(default_factory=list)
    sources_present: List[SignalSource] = field(default_factory=list)
    quality_score: float = 1.0

    packet_version: str = "v1"
    prev_hash: Optional[str] = None
    packet_hash: Optional[str] = None


# ============================================================
# Diagnostic Outputs (used in FRS-2)
# ============================================================

FindingType = Literal[
    "ecological_overshoot_risk",
    "material_scarcity_trend",
    "labor_imbalance_or_burnout_risk",
    "throughput_bottleneck_persistent",
    "quality_reliability_drift",
    "dependency_fragility_increase",
    "access_inequity_detected",
    "proto_market_or_coercion_risk",
    "governance_overload_or_capture_risk",
    "data_integrity_anomaly",
    "other",
]


@dataclass
class DiagnosticFinding:
    """
    FRS-2 output: a classified pathology or risk pattern derived from SignalPackets.
    """
    id: str
    node_id: str
    finding_type: FindingType

    severity: Severity
    scope: Scope
    persistence: Persistence
    confidence: Confidence

    detected_at: datetime
    related_tags: List[SemanticTag] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    indicators: Dict[str, float] = field(default_factory=dict)

    summary: str = ""
    rationale: str = ""


# ============================================================
# Constraint Modeling + Scenario Simulation (used in FRS-3)
# ============================================================

Horizon = Literal["near", "mid", "long"]  # near=weeks, mid=months, long=years (configurable)


@dataclass
class Constraint:
    """
    A binding or near-binding limit relevant to viability.
    """
    name: str
    domain: SignalDomain
    threshold: float
    unit: str
    direction: Literal["max", "min"]

    current_value: Optional[float] = None
    margin: Optional[float] = None                  # sign depends on direction
    confidence: Confidence = "medium"
    tags: List[SemanticTag] = field(default_factory=list)
    notes: str = ""


@dataclass
class ScenarioAssumption:
    key: str
    value: float
    unit: str = ""
    notes: str = ""


@dataclass
class ScenarioResult:
    scenario_id: str
    horizon: Horizon
    projected_metrics: Dict[str, float] = field(default_factory=dict)
    constraint_breaches: List[str] = field(default_factory=list)
    risk_score: float = 0.0                         # 0–1 (higher = worse)
    summary: str = ""


@dataclass
class ConstraintModel:
    id: str
    node_id: str
    created_at: datetime

    constraints: List[Constraint] = field(default_factory=list)
    assumptions: List[ScenarioAssumption] = field(default_factory=list)
    scenario_results: List[ScenarioResult] = field(default_factory=list)

    related_findings: List[str] = field(default_factory=list)
    notes: str = ""


# ============================================================
# Recommendations + Routing (used in FRS-4)
# ============================================================

TargetSystem = Literal["OAD", "COS", "ITC", "CDS", "FED"]

RecommendationType = Literal[
    "design_review_request",
    "workflow_stress_alert",
    "valuation_drift_flag",
    "training_priority_signal",
    "material_substitution_prompt",
    "dependency_risk_alert",
    "policy_review_prompt",
    "monitoring_directive",
    "federated_learning_share",
    "other",
]


@dataclass
class Recommendation:
    """
    Non-executive, typed recommendation emitted by FRS-4.
    """
    id: str
    node_id: str
    created_at: datetime

    target_system: TargetSystem
    recommendation_type: RecommendationType

    severity: Severity
    confidence: Confidence
    scope: Scope

    related_findings: List[str] = field(default_factory=list)
    related_model_ids: List[str] = field(default_factory=list)
    tags: List[SemanticTag] = field(default_factory=list)

    payload: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    rationale: str = ""


@dataclass
class RoutedSignal:
    recommendation_id: str
    target_system: TargetSystem
    dispatched_at: datetime
    delivery_status: Literal["queued", "delivered", "failed"] = "queued"
    notes: str = ""


# ============================================================
# Democratic Sensemaking Artifacts (used in FRS-5)
# ============================================================

ArtifactType = Literal[
    "dashboard_view",
    "risk_brief",
    "scenario_comparison",
    "deliberation_prompt",
    "public_summary",
    "technical_appendix",
]


@dataclass
class SensemakingArtifact:
    id: str
    node_id: str
    created_at: datetime
    artifact_type: ArtifactType

    title: str
    audience: Literal["public", "cds_participants", "technical"] = "cds_participants"

    related_findings: List[str] = field(default_factory=list)
    related_recommendations: List[str] = field(default_factory=list)
    related_models: List[str] = field(default_factory=list)

    content: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


# ============================================================
# Longitudinal Memory + Institutional Recall (used in FRS-6)
# ============================================================

MemoryRecordType = Literal[
    "baseline",
    "incident",
    "intervention",
    "outcome",
    "lesson",
    "policy_context",
    "design_lineage",
]


@dataclass
class MemoryRecord:
    id: str
    node_id: str
    created_at: datetime
    record_type: MemoryRecordType

    title: str
    tags: List[SemanticTag] = field(default_factory=list)

    evidence_refs: List[str] = field(default_factory=list)
    related_decisions: List[str] = field(default_factory=list)
    related_design_versions: List[str] = field(default_factory=list)

    narrative: str = ""
    quantified_outcomes: Dict[str, float] = field(default_factory=dict)
    notes: str = ""


# ============================================================
# Federated Intelligence Exchange (used in FRS-7)
# ============================================================

FederatedMessageType = Literal[
    "stress_signature",
    "best_practice",
    "design_success_case",
    "early_warning",
    "model_template",
    "memory_record_share",
]


@dataclass
class FederatedExchangeMessage:
    id: str
    message_type: FederatedMessageType
    created_at: datetime

    from_node_id: str
    to_scope: Literal["regional", "federation", "targeted_nodes"] = "regional"
    to_node_ids: List[str] = field(default_factory=list)

    tags: List[SemanticTag] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    related_findings: List[str] = field(default_factory=list)
    related_memory_records: List[str] = field(default_factory=list)
    related_recommendations: List[str] = field(default_factory=list)

    summary: str = ""
    notes: str = ""

```

***
