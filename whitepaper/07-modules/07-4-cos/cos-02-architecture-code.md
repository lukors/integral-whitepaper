### Formal COS Specification: Pseudocode + Math Sketches

High-Level Types: These are shared data structures used across COS modules (Python-style pseudocode; illustrative).

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime

# -------------------------------------------------------------------
# NOTE ON TYPE CONSISTENCY
# -------------------------------------------------------------------
# COS depends on canonical types defined in the OAD and ITC sections.
# Do NOT redefine those types here (to avoid schema drift).
#
# COS expects to consume:
# - DesignSpec, DesignVersion, OADValuationProfile (from OAD)
# - AccessValuation / RedemptionRecord (from ITC) when needed
#
# In this COS section we only define COS-specific objects.
# -------------------------------------------------------------------

# Canonical shared enums (match ITC)
SkillTier = Literal["low", "medium", "high", "expert"]
AccessMode = Literal["permanent_acquisition", "shared_use_lock", "service_use"]

TaskStatus = Literal["pending", "in_progress", "blocked", "done", "cancelled"]
MaterialFlowSource = Literal["internal_recycle", "external_procurement", "production_use", "loss_scrap"]

# -------------------------------------------------------------------
# 1) Tasks & workflow representation
# -------------------------------------------------------------------

@dataclass
class COSTaskDefinition:
    """
    A task template derived from OAD's labor-step decomposition, normalized for execution.
    Usually produced by COS Module 1 (planning) from an OAD-certified DesignVersion.
    """
    id: str
    version_id: str                       # OAD DesignVersion.id
    name: str                             # e.g. "frame_welding", "wheel_truing"
    description: str

    skill_tier: SkillTier
    estimated_hours_per_unit: float       # expected labor per unit for this step

    required_tools: List[str] = field(default_factory=list)
    required_workspaces: List[str] = field(default_factory=list)

    # Per-unit bill-of-materials *for this step* (not entire product BOM)
    required_materials_kg: Dict[str, float] = field(default_factory=dict)

    # Optional process-level ecological impact indicator (step-level; OAD may provide)
    process_eii: float = 0.0

    predecessors: List[str] = field(default_factory=list)  # task_definition_ids


@dataclass
class COSTaskInstance:
    """
    A concrete scheduled/executed instance of a task within a batch (or per unit).
    Produced and updated by COS Modules 2–5 (matching, execution, constraint balancing).
    """
    id: str
    definition_id: str
    batch_id: str
    node_id: str

    assigned_coop_id: str
    status: TaskStatus = "pending"

    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Realized execution metrics (used by ITC + FRS + COS learning)
    actual_hours: float = 0.0
    participants: List[str] = field(default_factory=list)  # member_ids
    block_reasons: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class COSProductionPlan:
    """
    The Work Breakdown Structure (WBS) for producing a batch of a given DesignVersion in a node.
    Produced by COS Module 1.
    """
    plan_id: str
    node_id: str
    version_id: str                       # OAD DesignVersion.id
    batch_id: str
    batch_size: int
    created_at: datetime

    tasks: Dict[str, COSTaskDefinition] = field(default_factory=dict)        # def_id -> definition
    task_instances: Dict[str, COSTaskInstance] = field(default_factory=dict) # inst_id -> instance

    # Aggregate expectations (used as “shadow plan” for ITC prior to execution reality)
    expected_labor_hours_by_skill: Dict[SkillTier, float] = field(default_factory=dict)
    expected_materials_kg: Dict[str, float] = field(default_factory=dict)    # whole-batch totals
    expected_cycle_time_hours: float = 0.0

    # Optional: early-warning prediction of likely constraints
    predicted_bottlenecks: List[str] = field(default_factory=list)           # def_ids
    notes: str = ""


# -------------------------------------------------------------------
# 2) Materials & inventory
# -------------------------------------------------------------------

@dataclass
class COSMaterialStock:
    """
    Node-level snapshot of a material inventory state.
    Used by COS Module 3 to plan internal allocation and detect shortfalls.
    """
    node_id: str
    material_name: str

    on_hand_kg: float
    reserved_kg: float = 0.0
    incoming_kg: float = 0.0
    min_safe_level_kg: float = 0.0

    # Optional ecological info per kg (typically comes from OAD/LCA databases)
    eii_per_kg: float = 0.0

    last_updated: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class COSMaterialLedgerEntry:
    """
    Traceable material movement record (append-only).
    This is COS's operational evidence stream and feeds ITC/FRS.
    """
    id: str
    node_id: str
    timestamp: datetime

    material_name: str
    delta_kg: float                         # + inflow, - consumption/loss
    source: MaterialFlowSource
    related_plan_id: Optional[str] = None
    related_task_instance_id: Optional[str] = None

    eii_per_kg: Optional[float] = None
    notes: str = ""


# -------------------------------------------------------------------
# 3) Throughput & capacity metrics
# -------------------------------------------------------------------

@dataclass
class COSCapacitySnapshot:
    """
    Real-time capacity view for planning windows (e.g., next week).
    Used by COS Modules 2 and 5, and exported to ITC Module 4 and FRS.
    """
    node_id: str
    timestamp: datetime

    available_hours_by_skill: Dict[SkillTier, float] = field(default_factory=dict)
    tool_utilization: Dict[str, float] = field(default_factory=dict)          # tool_id -> 0–1
    workspace_utilization: Dict[str, float] = field(default_factory=dict)     # workspace_id -> 0–1

    notes: str = ""


@dataclass
class COSThroughputMetrics:
    """
    Observed throughput + bottleneck metrics over a time window.
    Feeds COS Module 5 and the ITC/FRS feedback loops.
    """
    plan_id: str
    node_id: str
    window_start: datetime
    window_end: datetime

    completed_units: int
    avg_cycle_time_hours: float

    bottleneck_task_definitions: List[str] = field(default_factory=list)       # def_ids
    utilization_by_skill: Dict[SkillTier, float] = field(default_factory=dict) # 0–1
    utilization_by_tool: Dict[str, float] = field(default_factory=dict)        # 0–1
    notes: str = ""


# -------------------------------------------------------------------
# 4) Distribution / access records
# -------------------------------------------------------------------

@dataclass
class COSDistributionRecord:
    """
    Records how a specific produced unit is routed into access channels.
    This is where COS ties a unit to the ITC valuation snapshot used at the time.
    """
    id: str
    node_id: str
    version_id: str                       # OAD DesignVersion.id
    unit_serial: str
    timestamp: datetime

    access_mode: AccessMode
    assigned_center_id: Optional[str] = None      # Access Center / fleet / coop id

    # Link to ITC-side valuation object used for this distribution decision
    access_valuation_id: Optional[str] = None     # AccessValuation.item_id or record id (implementation choice)

    notes: str = ""

```

***
