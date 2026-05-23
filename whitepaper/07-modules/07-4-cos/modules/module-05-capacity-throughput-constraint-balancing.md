#### Module 5 (COS) — Capacity, Throughput & Constraint Balancing

**Purpose**
Identify and resolve bottlenecks in **skills, tools, materials, workspace, and timing**, and feed those constraints upstream to **ITC, OAD, and FRS** so valuation, design, and system health reflect what is *actually* happening on the ground.

**Role in the system**
Building on Modules 1–4:

- Module 1: knows *what* needs doing.
- Module 2: knows *who* can do it.
- Module 3: knows *what materials exist*.
- Module 4: knows *what’s really happening right now* (execution, delays, overruns).

Module 5 answers:

- Where is production truly constrained?
- Is the limiting factor skill, tools, materials, space, or time?
- How should we rebalance workflows now?
- What signals should we send to ITC (weighting/forecast), OAD (redesign), and FRS (stress/strain)?

This is COS’s *constraint radar + suggestion engine*.

------

**Types — Constraints & Signals**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from enum import Enum

class ConstraintType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    MATERIAL = "material"
    SPACE = "space"
    TIME = "time"

@dataclass
class COSConstraint:
    constraint_id: str
    plan_id: str
    node_id: str
    task_definition_id: Optional[str]   # which step is constrained (if any)
    constraint_type: ConstraintType
    severity: float                     # 0–1 (higher = worse)
    description: str
    suggested_actions: List[str] = field(default_factory=list)
```

**Signals to other systems:**

```python
@dataclass
class ITCConstraintSignal:
    plan_id: str
    node_id: str
    constraint_type: ConstraintType
    affected_task_definition_ids: List[str]
    suggested_weight_adjustments: Dict[str, float]  # task_def_id -> delta_weight_multiplier
    notes: str = ""

@dataclass
class OADConstraintSignal:
    plan_id: str
    node_id: str
    task_definition_id: str
    deviation_ratio: float
    description: str

@dataclass
class FRSConstraintSignal:
    plan_id: str
    node_id: str
    constraint_type: ConstraintType
    severity: float
    description: str
    metrics_snapshot: Dict[str, float]
```

**We reuse:**

- `COSProductionPlan`, `COSTaskDefinition`
- `COSTaskInstance`
- `COSExecutionMetrics`
- `TaskStatus` from Module 4

------

**Execution-layer consistency requirement**

To keep Module 5 robust, Module 4 should store a **structured block reason** when pausing/blocking tasks. Minimal addition:

```python
BlockReason = Literal["skill", "tool", "material", "space", "unknown"]

# Add to your execution-state COSTaskInstance
# block_reason: Optional[BlockReason] = None
```

If you don’t want to add a field, Module 5 can still fall back to parsing `notes`, but structured tags are strongly preferred.

------

1. Detect Task-Level Bottlenecks from Execution Metrics

```python
def detect_task_bottlenecks(
    plan: COSProductionPlan,
    exec_metrics: COSExecutionMetrics,
    deviation_threshold: float = 1.25,
    blocked_ratio_threshold: float = 0.20,
) -> List[COSConstraint]:
    """
    Identify task-level bottlenecks using:
    - estimate vs actual hours
    - fraction of instances in BLOCKED status
    """
    constraints: List[COSConstraint] = []

    # (A) Deviation-based constraints
    for def_id, pair in exec_metrics.estimate_vs_actual_hours.items():
        est = pair.get("estimated", 0.0)
        act = pair.get("actual", 0.0)
        if est <= 0:
            continue

        deviation = act / est
        if deviation >= deviation_threshold:
            constraints.append(
                COSConstraint(
                    constraint_id=f"{plan.plan_id}:dev:{def_id}",
                    plan_id=plan.plan_id,
                    node_id=plan.node_id,
                    task_definition_id=def_id,
                    constraint_type=ConstraintType.TIME,  # refined later
                    severity=min(1.0, max(0.0, deviation - 1.0)),
                    description=(
                        f"Task {def_id} exceeds estimated effort "
                        f"(actual/estimate = {deviation:.2f})."
                    ),
                    suggested_actions=[
                        "review workflow & tooling",
                        "consider redesign of this step (OAD)",
                        "consider targeted training",
                    ],
                )
            )

    # (B) Blocked-ratio constraints
    blocked_counts: Dict[str, int] = {}
    total_counts: Dict[str, int] = {}

    for inst in plan.task_instances.values():
        def_id = inst.definition_id
        total_counts[def_id] = total_counts.get(def_id, 0) + 1
        blocked_counts.setdefault(def_id, 0)

        if inst.status == TaskStatus.BLOCKED:
            blocked_counts[def_id] += 1

    for def_id, total in total_counts.items():
        if total <= 0:
            continue

        blocked_ratio = blocked_counts.get(def_id, 0) / total
        if blocked_ratio >= blocked_ratio_threshold:
            constraints.append(
                COSConstraint(
                    constraint_id=f"{plan.plan_id}:blocked:{def_id}",
                    plan_id=plan.plan_id,
                    node_id=plan.node_id,
                    task_definition_id=def_id,
                    constraint_type=ConstraintType.TIME,  # refined later
                    severity=min(1.0, blocked_ratio),
                    description=(
                        f"Task {def_id} has high blocked ratio "
                        f"({blocked_ratio:.2%} blocked)."
                    ),
                    suggested_actions=[
                        "investigate cause of blocking (skill/tool/material/space)",
                        "re-sequence tasks to avoid contention",
                        "adjust capacity or training for this step",
                    ],
                )
            )

    return constraints
```

------

2. Refine Constraint Types

Preferred: use `inst.block_reason` (structured). Fallback: parse `inst.notes`.

```python
def refine_constraint_types(
    plan: COSProductionPlan,
    constraints: List[COSConstraint],
    max_space_capacity: Optional[int] = None,
) -> None:
    """
    Refine constraint types using blocked task reasons.
    Prefers structured block_reason fields; falls back to notes.
    """
    by_def: Dict[str, List[COSTaskInstance]] = {}
    for inst in plan.task_instances.values():
        by_def.setdefault(inst.definition_id, []).append(inst)

    for c in constraints:
        if not c.task_definition_id:
            continue

        instances = by_def.get(c.task_definition_id, [])
        blocked_instances = [i for i in instances if i.status == TaskStatus.BLOCKED]

        # --- 1) Structured block_reason (preferred) ---
        reasons = []
        for i in blocked_instances:
            br = getattr(i, "block_reason", None)
            if br:
                reasons.append(br)

        # If we have structured reasons, classify by majority/priority
        if reasons:
            if "material" in reasons:
                c.constraint_type = ConstraintType.MATERIAL
                c.suggested_actions.append("check COS Module 3 (stock/procurement/substitution)")
            elif "tool" in reasons:
                c.constraint_type = ConstraintType.TOOL
                c.suggested_actions.append("schedule maintenance / add redundant tool capacity")
            elif "skill" in reasons:
                c.constraint_type = ConstraintType.SKILL
                c.suggested_actions.append("trigger targeted training / apprenticeship")
            elif "space" in reasons:
                c.constraint_type = ConstraintType.SPACE
                c.suggested_actions.append("re-sequence tasks to reduce workspace contention")
            else:
                c.constraint_type = ConstraintType.TIME
            continue

        # --- 2) Notes parsing fallback ---
        notes_blob = " ".join(i.notes.lower() for i in blocked_instances)

        if any(k in notes_blob for k in ["missing material", "no stock", "waiting for material"]):
            c.constraint_type = ConstraintType.MATERIAL
            c.suggested_actions.append("check COS Module 3 (stock/procurement/substitution)")
        elif any(k in notes_blob for k in ["tool unavailable", "machine down", "maintenance"]):
            c.constraint_type = ConstraintType.TOOL
            c.suggested_actions.append("schedule maintenance / add redundant tool capacity")
        elif any(k in notes_blob for k in ["no qualified worker", "skill gap", "no volunteer"]):
            c.constraint_type = ConstraintType.SKILL
            c.suggested_actions.append("trigger targeted training / apprenticeship")
        elif max_space_capacity is not None:
            active_or_blocked = [
                i for i in instances if i.status in {TaskStatus.ACTIVE, TaskStatus.BLOCKED}
            ]
            if len(active_or_blocked) > max_space_capacity:
                c.constraint_type = ConstraintType.SPACE
                c.suggested_actions.append("re-sequence tasks to avoid workspace saturation")
```

------

3. **Generate Signals for ITC, OAD, and FRS**

3.1 To ITC — conservative defaults

Weight nudges should **default to SKILL constraints**, because ITC weighting is primarily meant to respond to scarcity of *labor capability*, not to tool breakdowns (which COS can fix) or material shortages (which COS/OAD should address first).

```python
def build_itc_constraint_signals(
    constraints: List[COSConstraint],
    weight_delta_base: float = 0.10,
    only_skill_constraints: bool = True,
) -> List[ITCConstraintSignal]:
    """
    Generate advisory ITC signals.
    Default: only skill constraints produce weight adjustment suggestions.
    """
    signals: List[ITCConstraintSignal] = []

    for c in constraints:
        if not c.task_definition_id:
            continue
        if only_skill_constraints and c.constraint_type != ConstraintType.SKILL:
            continue

        delta = weight_delta_base * c.severity

        signals.append(
            ITCConstraintSignal(
                plan_id=c.plan_id,
                node_id=c.node_id,
                constraint_type=c.constraint_type,
                affected_task_definition_ids=[c.task_definition_id],
                suggested_weight_adjustments={c.task_definition_id: delta},
                notes="Advisory signal from COS Module 5 (bounded by CDS in ITC Module 2/4).",
            )
        )

    return signals
```

3.2 To OAD — redesign triggers

```python
def build_oad_constraint_signals(
    constraints: List[COSConstraint],
    min_severity: float = 0.25,
) -> List[OADConstraintSignal]:
    signals: List[OADConstraintSignal] = []

    for c in constraints:
        if not c.task_definition_id:
            continue
        if c.severity < min_severity:
            continue

        # TIME/TOOL/MATERIAL are common redesign triggers.
        if c.constraint_type in {ConstraintType.TIME, ConstraintType.TOOL, ConstraintType.MATERIAL}:
            signals.append(
                OADConstraintSignal(
                    plan_id=c.plan_id,
                    node_id=c.node_id,
                    task_definition_id=c.task_definition_id,
                    deviation_ratio=1.0 + c.severity,
                    description=f"Constraint suggests redesign candidate: {c.description}",
                )
            )

    return signals
```

3.3 To FRS — system health

```python
def build_frs_constraint_signals(
    constraints: List[COSConstraint],
    exec_metrics: COSExecutionMetrics,
) -> List[FRSConstraintSignal]:
    signals: List[FRSConstraintSignal] = []

    for c in constraints:
        signals.append(
            FRSConstraintSignal(
                plan_id=c.plan_id,
                node_id=c.node_id,
                constraint_type=c.constraint_type,
                severity=c.severity,
                description=c.description,
                metrics_snapshot={
                    "total_active_hours": exec_metrics.total_active_seconds / 3600.0,
                    "wip_tasks": exec_metrics.wip_tasks,
                    "blocked_tasks": exec_metrics.blocked_tasks,
                },
            )
        )

    return signals
```

------

4. Orchestration

```python
def run_capacity_and_constraint_analysis(
    plan: COSProductionPlan,
    exec_metrics: COSExecutionMetrics,
    max_space_capacity: Optional[int] = None,
) -> Dict[str, List]:
    """
    COS Module 5 — Capacity, Throughput & Constraint Balancing
    """
    constraints = detect_task_bottlenecks(plan, exec_metrics)
    refine_constraint_types(plan, constraints, max_space_capacity=max_space_capacity)

    itc_signals = build_itc_constraint_signals(constraints)
    oad_signals = build_oad_constraint_signals(constraints)
    frs_signals = build_frs_constraint_signals(constraints, exec_metrics)

    return {
        "constraints": constraints,
        "itc_signals": itc_signals,
        "oad_signals": oad_signals,
        "frs_signals": frs_signals,
    }
```

------
**Math Sketch — Bottleneck Identification & Severity**

Let:
- $S = \{ s_1, \dots, s_n \}$ be the set of task types (definitions).
- For each step $s$:
  - Estimated total hours:

$$
T^{est}_s = \sum_{i \in I_s} t^{est}_i
$$

  - Actual total hours:

$$
T^{act}_s = \sum_{i \in I_s} t^{act}_i
$$

  - Deviation ratio:

$$
D_s = \frac{T^{act}_s}{\max(T^{est}_s, \epsilon)}
$$

- Let $B_s$ = number of blocked instances of step $s$.
- Let $N_s$ = total instances of step $s$.
- Blocked ratio:

$$
R_s^{blocked} = \frac{B_s}{\max(N_s, 1)}
$$

Define a **severity score** for step $s$:

$$
\text{severity}_s = \min\Big(1,\; \alpha \cdot (D_s - 1)_+ + \beta \cdot R_s^{blocked} \Big)
$$

where:
- $(x)_+ = \max(x, 0)$
- $\alpha, \beta$ are tuning constants (e.g., give more weight to time deviation or blocking)
- $\text{severity}_s \in [0, 1]$

Steps with high severity are candidates for:
- **OAD redesign** (if the issue is structural)
- **ITC weighting/training adjustment** (if it's a skill bottleneck)
- **COS local fixes** (new tools, better sequencing)
- **FRS systemic flags** (if this pattern persists across plans)

Once the most severe step is identified (or top-$k$), that step is (for this batch) the **bottleneck**: its capacity constrains total output.

---

**Plain-Language Example (Still Bicycle / Guitar Behind the Scenes)**

- The plan says each **wheel truing** should take 0.5 hours.
- Execution data shows:
  - $D_{\text{truing}} = 1.6$ (it's taking 60% longer)
  - $R^{blocked}_{\text{truing}} = 0.35$ (35% of instances end up blocked at some point)
- Module 5 computes a high severity score and classifies it:
  - notes show "no qualified worker," "tool unavailable," "waiting for materials"
  - If notes skew toward "no qualified worker" → SKILL constraint
  - If toward "tool unavailable" → TOOL constraint, etc.
- It then sends:
  - To **ITC**: "Consider a temporary +0.15 weight increase on truing tasks; highlight these tasks for training volunteers."
  - To **OAD**: "Step `wheel_truing` is consistently 60% over estimate; evaluate design/fixturing."
  - To **FRS**: "Chronic skill bottleneck at truing; potential burnout risk and production instability."

Over time:
- Training expands, tools improve, design is simplified.
- The severity score drops, throughput stabilizes.
- ITC weighting for that step can relax, and the **access-value of the good trends downward**, reflecting real systemic efficiency, not price games.
