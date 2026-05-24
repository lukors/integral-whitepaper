### Formal ITC Specification: Pseudocode + Math Sketches

This section presents an implementation-oriented view of the **Integral Time Credit (ITC) system**. The goal is not to prescribe a specific language or software stack, but to demonstrate that ITC’s contribution accounting and access-valuation logic can be expressed as explicit **data structures**, **functions**, and **bounded mathematical relations**—in a way that is auditable, non-coercive, and compatible with Integral’s broader cybernetic architecture.

What follows is not production code. It is structured pseudocode and simple math intended to make ITC **computable and buildable**:

- how operational labor is captured and verified (Module 1)
- how contextual weighting is applied within democratic bounds (Module 2)
- how balances decay to prevent accumulation (Module 3)
- how labor demand is forecast without compelling participation (Module 4)
- how access obligations are computed from real design, production, and ecological signals (Module 5)
- how federated equivalence is handled as **interpretation bands**, not exchange (Module 6)
- how coercion and proto-market behavior are detected and escalated through governance (Module 7)
- how all ITC-relevant events are recorded in an append-only audit layer (Module 8)
- and how ITC synchronizes with CDS, OAD, COS, and FRS without becoming a policy authority (Module 9)

To support these modules, we begin with a set of shared **high-level types**. These types define the canonical objects ITC operates on:

- `LaborEvent` and `WeightedLaborRecord` (contribution recognition)
- `ITCAccount` and `DecayRule` (non-accumulative balance dynamics)
- `LaborDemandForecast` (feed-forward need anticipation)
- `AccessValuation` and `RedemptionRecord` (access obligation and extinguishment)
- `EquivalenceBand` (cross-node interpretation normalization)
- `EthicsEvent` (anti-coercion detection and escalation)
- `LedgerEntry` (tamper-evident audit and traceability)
- and signal snapshots from CDS, OAD, COS, and FRS used for coordination and bounded recalibration

These objects are the computational foundation of ITC. Every crediting event, decay update, access valuation, ethical flag, and coordination adjustment is represented as a transformation over these types—making ITC a **transparent cybernetic accounting system**, not a currency, not a market, and not a command apparatus.

**High-Level Types (shared architecture foundation for ITC)**

~~~python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime


# --------------------------------
# 1. Labor Events & Weighting
# --------------------------------

SkillTier = Literal["low", "medium", "high", "expert"]


@dataclass
class LaborEvent:
    """
    Raw operational labor captured from COS / cooperatives.
    No value assigned yet — this is a 'neutral' contribution event.
    """
    id: str
    member_id: str
    coop_id: str
    task_id: str
    task_label: str
    node_id: str

    start_time: datetime
    end_time: datetime
    hours: float

    skill_tier: SkillTier
    context: Dict[str, Any]                 # e.g. {"urgency_score": 0.7, "eco_sensitive": True, ...}
    verified_by: List[str]                  # peer or supervisor IDs
    verification_timestamp: datetime
    metadata: Dict[str, Any]                # COS linkage, tags, etc.


@dataclass
class WeightedLaborRecord:
    """
    LaborEvent after Skill & Context Weighting.
    Represents a credited contribution signal in ITC terms.
    """
    id: str                                  # distinct record id for audit & references
    event_id: str
    member_id: str
    node_id: str

    base_hours: float
    weight_multiplier: float                 # final bounded multiplier
    weighted_hours: float                    # base_hours * weight_multiplier

    breakdown: Dict[str, float]              # {"skill_factor": 1.3, "scarcity_factor": 1.1, ...}
    created_at: datetime


# --------------------------------
# 2. ITC Accounts & Decay
# --------------------------------

@dataclass
class DecayRule:
    """
    Democratically defined decay pattern for ITC balances.
    """
    id: str
    label: str
    inactivity_grace_days: float             # no decay within grace window
    half_life_days: float                    # exponential half-life beyond grace
    min_balance_protected: float             # small protected floor (optional)
    max_annual_decay_fraction: float         # safety bound (e.g. 0.30 for max 30%/yr)
    effective_from: datetime


@dataclass
class ITCAccount:
    """
    Member-level ITC balance and history.
    """
    id: str
    member_id: str
    node_id: str

    balance: float
    last_decay_applied_at: datetime
    active_decay_rule_id: str

    total_earned: float = 0.0
    total_redeemed: float = 0.0
    total_decayed: float = 0.0


# --------------------------------
# 3. Labor Forecasting & Needs
# --------------------------------

@dataclass
class LaborDemandForecast:
    """
    Forecasted labor demand across skill tiers and sectors.
    Derived from COS task queues, OAD pipelines, and FRS signals.
    """
    node_id: str
    generated_at: datetime
    horizon_days: int

    demand_by_skill: Dict[SkillTier, float]     # hours
    demand_by_sector: Dict[str, float]          # hours by sector label

    bottleneck_skills: List[SkillTier]
    notes: str = ""


# --------------------------------
# 4. Access Valuation & Redemption
# --------------------------------

AccessMode = Literal["permanent_acquisition", "shared_use_lock", "service_use"]


@dataclass
class AccessValuation:
    """
    Computed ITC access obligation for a specific good/service instance.
    This is the non-market access-value object (NOT a price).
    """
    item_id: str                               # e.g. "bicycle-rev3-serial-ABC123"
    design_version_id: str                     # link to OAD-certified version
    node_id: str

    # Core labor backbone (usually weighted hours)
    base_weighted_labor_hours: float

    # Hours-equivalent adjustments (bounded and explainable)
    eco_burden_adjustment: float               # + hours-equiv
    material_scarcity_adjustment: float        # + hours-equiv
    repairability_credit: float                # - hours-equiv
    longevity_credit: float                    # - hours-equiv

    final_itc_cost: float                      # final access obligation in ITCs

    computed_at: datetime
    valid_until: Optional[datetime]
    policy_snapshot_id: str                    # which CDS policy snapshot bounded this valuation
    rationale: Dict[str, Any] = field(default_factory=dict)  # traceable breakdown


@dataclass
class RedemptionRecord:
    """
    Record of a member redeeming ITCs for access to a good or service.
    """
    id: str
    member_id: str
    node_id: str
    item_id: str

    itc_spent: float
    redemption_time: datetime
    redemption_type: AccessMode
    expires_at: Optional[datetime]             # for shared-use locks or timed services

    access_valuation_snapshot: AccessValuation


# --------------------------------
# 5. Internodal Interpretation (Equivalence Bands)
# --------------------------------

@dataclass
class EquivalenceBand:
    """
    Federated interpretation profile used at access-computation time.
    This does NOT convert balances; it adjusts local interpretation parameters
    within CDS-approved bounds.
    """
    home_node_id: str
    local_node_id: str

    labor_context_factor: float                # bounded (e.g. 0.9–1.1)
    eco_context_factor: float                  # bounded (e.g. 0.9–1.1)
    updated_at: datetime
    notes: str = ""


# --------------------------------
# 6. Ethics & Ledger Records
# --------------------------------

EthicsSeverity = Literal["info", "warning", "critical"]
EthicsStatus = Literal["open", "under_review", "resolved"]

LedgerEntryType = Literal[
    "labor_event_recorded",
    "labor_weight_applied",
    "itc_credited",
    "itc_decayed",
    "access_value_quoted",
    "access_redeemed",
    "equivalence_band_applied",
    "ethics_flag_created",
    "ethics_flag_resolved",
    "policy_updated",
]


@dataclass
class EthicsEvent:
    """
    Records fairness / anti-coercion issues surfaced by FRS + ITC monitoring.
    Detection only; enforcement is handled through CDS processes.
    """
    id: str
    node_id: str
    timestamp: datetime
    severity: EthicsSeverity

    description: str
    involved_member_ids: List[str] = field(default_factory=list)
    involved_coop_ids: List[str] = field(default_factory=list)
    rule_violations: List[str] = field(default_factory=list)
    status: EthicsStatus = "open"
    resolution_notes: str = ""


@dataclass
class LedgerEntry:
    """
    Generic ITC ledger entry for auditability.
    Append-only; used for transparency, diagnosis, and reproducibility.
    """
    id: str
    timestamp: datetime
    entry_type: LedgerEntryType
    node_id: str

    member_id: Optional[str] = None
    related_ids: Dict[str, str] = field(default_factory=dict)   # e.g. {"event_id": "...", "item_id": "...", "coop_id": "..."}
    details: Dict[str, Any] = field(default_factory=dict)       # JSON-like payload


# --------------------------------
# 7. Integration Signals (CDS / OAD / COS / FRS)
# --------------------------------

@dataclass
class OADValuationProfile:
    """
    Summarized design intelligence emitted by OAD (copied here for ITC convenience).
    """
    version_id: str
    material_intensity: float
    repairability: float
    bill_of_materials: Dict[str, float]
    embodied_energy: float
    expected_lifespan_hours: float
    estimated_labor_hours: float
    ecological_score: float
    notes: str = ""


@dataclass
class COSWorkloadSignal:
    """
    Snapshot from COS: real production/maintenance workload conditions.
    """
    node_id: str
    generated_at: datetime

    total_hours_by_skill: Dict[SkillTier, float]
    backlog_hours_by_skill: Dict[SkillTier, float]
    throughput_constraints: Dict[str, float]           # e.g. {"bike_assembly": 0.8}
    material_scarcity_index: Dict[str, float]          # e.g. {"aluminum": 0.3, "steel": 0.05}


@dataclass
class FRSConstraintSignal:
    """
    Feedback from FRS: ecological pressure, systemic stress, behavioral anomalies.
    """
    node_id: str
    generated_at: datetime

    eco_pressure_index: float                          # 0–1 (higher = more strain)
    material_pressure_index: Dict[str, float]          # per material
    fairness_anomaly_score: float                      # 0–1
    notes: str = ""


@dataclass
class CDSPolicySnapshot:
    """
    CDS-resolved parameters that bound ITC behavior at a given time.
    """
    id: str
    timestamp: datetime

    global_max_weight_multiplier: float
    min_weight_multiplier: float
    decay_rule_ids: List[str]
    fairness_rules: Dict[str, Any]                     # e.g. {"no_side_deals": True}
    equivalence_policy_notes: str = ""
~~~

***
