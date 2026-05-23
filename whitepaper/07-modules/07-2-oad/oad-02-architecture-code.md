### Formal OAD Specification: Pseudocode + Math Sketches

This section gives a concrete, implementation-oriented view of the **Open Access Design System (OAD)**. The goal is not to prescribe a specific programming language or framework, but to show that OAD’s workflow can be expressed as explicit **data structures**, **functions**, and **simple mathematical relations**:

- how designs enter the system in structured form
- how they are collaboratively refined and versioned
- how **material & ecological coefficients** are computed
- how lifecycle and maintainability are modeled
- how labor is decomposed into computable steps for COS and ITC
- how feasibility and systems integration are simulated
- how designs are optimized, certified, and archived for reuse across the federation

OAD is not a one-way pipeline. Certified designs stored in the commons (Module 10) are continuously pulled back into the collaborative workspace (Module 2) for **reuse and local adaptation**, while **FRS operational feedback** can recalibrate ecological coefficients, lifecycle assumptions, labor estimates, optimization targets, and even certification status when real-world performance diverges from modeled expectations.

All code below is Python-style pseudocode, meant to illustrate structure and logic rather than serve as production code.

***

**High-Level Types**

First, shared data structures are defined for:

- design specifications and versions
- ecological and material assessments
- lifecycle and maintainability models
- labor-step profiles (used directly by COS and ITC)
- simulation and integration checks
- optimization results, certification records, and repository entries

These are the core objects OAD modules manipulate and emit.

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime


# ----------------------------
# Core Design Entities
# ----------------------------

@dataclass
class DesignSpec:
    """
    Initial structured submission: the 'idea' made computable.
    """
    id: str
    title: str
    description: str
    creator_id: str
    created_at: datetime

    functional_goals: List[str] = field(default_factory=list)   # e.g. ["desalinate 50 L/day", "low maintenance"]
    components: List[str] = field(default_factory=list)         # named subsystems / parts
    cad_files: List[str] = field(default_factory=list)          # URIs / hashes for geometry
    materials: List[str] = field(default_factory=list)          # initial assumed materials
    env_assumptions: Dict[str, Any] = field(default_factory=dict)       # e.g. {"climate": "coastal", "salt_ppm": 8000}
    performance_criteria: Dict[str, Any] = field(default_factory=dict)  # e.g. {"flow_rate_lph": 50, "max_power_w": 120}
    safety_considerations: List[str] = field(default_factory=list)
    maintenance_expectations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)      # tags, node, sector, etc.


DesignVersionStatus = Literal[
    "draft",
    "under_review",
    "optimized",
    "ready_for_certification",
    "certified",
    "deprecated",
]


@dataclass
class DesignVersion:
    """
    Concrete design variant under active development, review, or certification.
    """
    id: str
    spec_id: str
    parent_version_id: Optional[str]
    label: str                     # e.g. "v0.3-bamboo-frame"
    created_at: datetime
    authors: List[str] = field(default_factory=list)

    cad_files: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)    # parametric knobs / geometry
    change_log: str = ""
    status: DesignVersionStatus = "draft"

    superseded_by_version_id: Optional[str] = None              # useful for re-certification chains


# ----------------------------
# Material & Ecological Assessment Types
# ----------------------------

@dataclass
class MaterialProfile:
    """
    Quantitative material breakdown for a design version.
    Used by ecological assessment, COS planning, and ITC.
    """
    version_id: str
    materials: List[str] = field(default_factory=list)
    quantities_kg: Dict[str, float] = field(default_factory=dict)  # material -> kg

    embodied_energy_mj: float = 0.0
    embodied_carbon_kg: float = 0.0

    recyclability_index: float = 0.0     # 0–1 (higher = more recyclable)
    toxicity_index: float = 0.0          # 0–1 (higher = more toxic)
    scarcity_index: float = 0.0          # 0–1 (higher = more constrained)


@dataclass
class EcoAssessment:
    """
    Aggregated ecological impact evaluation, normalized for comparison.
    Lower eco_score is better.
    """
    version_id: str
    embodied_energy_norm: float = 0.0    # 0–1
    carbon_intensity_norm: float = 0.0   # 0–1
    toxicity_norm: float = 0.0           # 0–1
    recyclability_norm: float = 0.0      # 0–1 (higher is better)
    water_use_norm: float = 0.0          # 0–1
    land_use_norm: float = 0.0           # 0–1
    repairability_norm: float = 0.0      # 0–1 (higher is better)

    eco_score: float = 0.0               # composite; lower = better
    passed: bool = False
    notes: str = ""


# ----------------------------
# Lifecycle & Maintainability Types
# ----------------------------

@dataclass
class LifecycleModel:
    """
    Expected lifetime behavior of the design, including maintenance burden.
    Recalibrated over time using FRS operational feedback.
    """
    version_id: str
    expected_lifetime_years: float = 0.0
    usage_cycles_before_overhaul: float = 0.0
    maintenance_interval_days: float = 0.0
    maintenance_labor_hours_per_interval: float = 0.0
    disassembly_hours: float = 0.0
    refurb_cycles_possible: int = 0
    dominant_failure_modes: List[str] = field(default_factory=list)

    lifecycle_burden_index: float = 0.0  # 0–1, higher = more labor/risk


# ----------------------------
# Labor-Step Decomposition Types (OAD → COS/ITC)
# ----------------------------

SkillTier = Literal["low", "medium", "high", "expert"]


@dataclass
class LaborStep:
    """
    A single production or maintenance step in the design's labor plan.
    """
    name: str
    estimated_hours: float
    skill_tier: SkillTier
    tools_required: List[str] = field(default_factory=list)
    sequence_index: int = 0
    safety_notes: str = ""


@dataclass
class LaborProfile:
    """
    Full decomposed labor plan for a design version.
    Primary input to COS scheduling and ITC access-value calculation.
    """
    version_id: str
    production_steps: List[LaborStep] = field(default_factory=list)
    maintenance_steps: List[LaborStep] = field(default_factory=list)

    total_production_hours: float = 0.0
    total_maintenance_hours_over_life: float = 0.0

    hours_by_skill_tier: Dict[str, float] = field(default_factory=dict)
    ergonomics_flags: List[str] = field(default_factory=list)
    risk_notes: str = ""


# ----------------------------
# Simulation, Integration, Optimization, Certification, Repository
# ----------------------------

@dataclass
class SimulationResult:
    """
    Technical feasibility and safety simulation outputs.
    """
    version_id: str
    scenarios: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    feasibility_score: float = 0.0             # 0–1, higher is better
    safety_margins: Dict[str, float] = field(default_factory=dict)
    manufacturability_flags: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)


@dataclass
class IntegrationCheck:
    """
    Compatibility and systems-architecture evaluation.
    """
    version_id: str
    compatible_systems: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    circular_loops: List[str] = field(default_factory=list)
    integration_score: float = 0.0             # 0–1


@dataclass
class OptimizationResult:
    """
    Snapshot of an optimization run comparing before/after metrics.
    """
    base_version_id: str
    optimized_version_id: str
    objective_value: float
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    improvement_summary: str = ""


CertificationStatus = Literal["certified", "revoked", "pending"]


@dataclass
class CertificationRecord:
    """
    Certification gate for a design version.
    Can be revoked or superseded based on FRS operational feedback.
    """
    version_id: str
    certified_at: datetime
    certified_by: List[str] = field(default_factory=list)
    criteria_passed: List[str] = field(default_factory=list)
    criteria_failed: List[str] = field(default_factory=list)
    documentation_bundle_uri: str = ""
    status: CertificationStatus = "pending"


@dataclass
class RepoEntry:
    """
    Index entry for the knowledge commons / design repository.
    """
    version_id: str
    spec_id: str
    tags: List[str] = field(default_factory=list)
    climates: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)
    reuse_count: int = 0
    variants: List[str] = field(default_factory=list)  # related version_ids


# ----------------------------
# ITC-Relevant Valuation Payload (Required OAD Output)
# ----------------------------

@dataclass
class OADValuationProfile:
    """
    Condensed ITC-relevant snapshot of a certified design version.
    Derived from MaterialProfile, EcoAssessment, LifecycleModel, and LaborProfile.
    """
    version_id: str

    # Materials & ecology (normalized + absolute where useful)
    material_intensity_norm: float = 0.0       # 0–1 (material mass / benchmark)
    ecological_score: float = 0.0              # composite eco assessment (lower = better)
    bill_of_materials: Dict[str, float] = field(default_factory=dict)  # {material: kg}
    embodied_energy_mj: float = 0.0
    embodied_carbon_kg: float = 0.0

    # Lifetime & labor
    expected_lifespan_hours: float = 0.0
    production_labor_hours: float = 0.0
    maintenance_labor_hours_over_life: float = 0.0

    # Summary fields for COS/ITC heuristics
    hours_by_skill_tier: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

```
