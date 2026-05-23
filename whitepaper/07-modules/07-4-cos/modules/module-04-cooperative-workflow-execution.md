#### Module 4 (COS) — Cooperative Workflow Execution

**Purpose**
Coordinate real-time execution of production work: which tasks are active, who’s working on what, how long it’s taking, where things are blocked, and how actual production deviates from the plan. This is the **live orchestration layer** that turns static plans into moving processes.

**Role in the system**
Module 4 sits between:

- **Module 1/2/3** (planning, labor matching, materials)
   and
- **Module 5/6/7/9** (bottleneck balancing, distribution, QA, transparency).

It:

- tracks each **task instance** through its lifecycle (pending → active → blocked → completed),
- records actual **labor time** by participant (and later, by skill tier once verified/weighted),
- surfaces **real-time WIP** (work in progress) and delays,
- emits **candidate labor events** to ITC for capture/verification/weighting,
- provides **throughput + deviation data** to Module 5 and to ITC valuation realism.

Think of it as the **production cockpit**: everyone can see what’s happening, adjust voluntarily, and keep flow smooth—without managers or wage incentives.

***

**Types (Execution Layer)**

We extend the COS types already defined, without renaming your existing `COSTaskInstance.id`.

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import time


class TaskStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class COSTaskInstance:
    """
    Execution-state extension for a task instance.
    (In a real implementation this would be merged into your earlier COSTaskInstance
    or stored as an execution-state object keyed by instance_id.)
    """
    id: str
    definition_id: str
    batch_id: str

    assigned_coop_id: str
    participants: List[str] = field(default_factory=list)  # member IDs

    status: TaskStatus = TaskStatus.PENDING

    # Timing
    active_seconds: float = 0.0
    last_started_ts: Optional[float] = None  # epoch seconds

    # Optional: why blocked, what changed, etc.
    notes: str = ""


@dataclass
class COSExecutionMetrics:
    plan_id: str
    node_id: str

    total_active_seconds: float
    total_completed_tasks: int
    wip_tasks: int
    blocked_tasks: int

    avg_cycle_time_seconds: Optional[float]

    # deviations from estimates by task definition id
    estimate_vs_actual_hours: Dict[str, Dict[str, float]]  # {def_id: {"estimated": h_e, "actual": h_a}}
    notes: str = ""
```

We assume `COSProductionPlan` already exists from Module 1:

```python
@dataclass
class COSProductionPlan:
    plan_id: str
    node_id: str
    tasks: Dict[str, "COSTaskDefinition"]             # def_id -> definition
    task_instances: Dict[str, COSTaskInstance]        # instance_id -> instance
```

And `COSTaskDefinition`:

```python
@dataclass
class COSTaskDefinition:
    id: str
    name: str
    skill_tier: str
    estimated_hours: float
    required_materials_kg: Dict[str, float]
    # plus tools, EII, predecessors, etc.
```

***

1. Assign / Update Task Instances

Module 2 suggests; Module 4 records the actual participation at execution time.

```python
def add_participant(plan: COSProductionPlan, task_instance_id: str, member_id: str) -> None:
    inst = plan.task_instances[task_instance_id]
    if member_id not in inst.participants:
        inst.participants.append(member_id)
```

***

2. Start, Pause, Complete Tasks

```python
def start_task_instance(plan: COSProductionPlan, task_instance_id: str) -> None:
    inst = plan.task_instances[task_instance_id]
    if inst.status in {TaskStatus.PENDING, TaskStatus.BLOCKED}:
        inst.status = TaskStatus.ACTIVE
        inst.last_started_ts = time.time()

def pause_task_instance(plan: COSProductionPlan, task_instance_id: str, reason: str = "") -> None:
    inst = plan.task_instances[task_instance_id]
    if inst.status == TaskStatus.ACTIVE and inst.last_started_ts is not None:
        now = time.time()
        inst.active_seconds += max(0.0, now - inst.last_started_ts)
        inst.last_started_ts = None
        inst.status = TaskStatus.BLOCKED
        if reason:
            inst.notes += f"\nBlocked: {reason}"
```

Completing a task and emitting candidate labor events to ITC

Key consistency fix: COS should emit **candidate labor claims** with clean timestamps and references, and let **ITC Module 1** handle verification and official `LaborEvent` creation.

```python
def complete_task_instance(
    plan: COSProductionPlan,
    task_instance_id: str,
    emit_labor_claims_fn,
    coop_id: str,
    proposed_verifiers: Optional[List[str]] = None,
) -> None:
    """
    Mark task instance COMPLETED, accumulate time, and emit candidate labor claims to ITC.

    emit_labor_claims_fn:
      callback into ITC intake, e.g. emit_labor_claims_fn(list_of_claim_dicts)
      ITC Module 1 will authenticate + verify + mint official LaborEvent records.

    proposed_verifiers:
      optional peer/supervisor IDs suggested by COS (ITC still enforces verifier rules).
    """
    inst = plan.task_instances[task_instance_id]

    # finalize timing if currently active
    if inst.status == TaskStatus.ACTIVE and inst.last_started_ts is not None:
        now = time.time()
        inst.active_seconds += max(0.0, now - inst.last_started_ts)
        inst.last_started_ts = None

    inst.status = TaskStatus.COMPLETED

    # derive total hours worked on this task instance
    total_hours = inst.active_seconds / 3600.0
    if total_hours <= 0.0 or not inst.participants:
        return

    task_def = plan.tasks[inst.definition_id]

    # simple split: equal share (you can replace later with per-person timers)
    hours_per_member = total_hours / len(inst.participants)

    start_time = datetime.utcnow()  # placeholder: ideally use actual start/stop times captured
    end_time = datetime.utcnow()

    claims = []
    for member_id in inst.participants:
        claims.append({
            "member_id": member_id,
            "coop_id": coop_id,
            "node_id": plan.node_id,
            "task_id": inst.definition_id,
            "task_label": task_def.name,
            "start_time": start_time,
            "end_time": end_time,
            "hours": hours_per_member,
            "skill_tier": task_def.skill_tier,      # initial tier; ITC may refine via policy
            "context": {"plan_id": plan.plan_id, "batch_id": inst.batch_id},
            "proposed_verifiers": proposed_verifiers or [],
            "metadata": {"task_instance_id": inst.id},
        })

    emit_labor_claims_fn(claims)
```

> **Note:** This is intentionally “pre-verification.” COS is generating **structured labor claims**; ITC Module 1 is the canonical gate that verifies and records official events.

***

3. **Execution Metrics & Deviations**

```python
def compute_execution_metrics(plan: COSProductionPlan) -> COSExecutionMetrics:
    total_active_seconds = 0.0
    total_completed_tasks = 0
    wip_tasks = 0
    blocked_tasks = 0

    agg_estimated_hours: Dict[str, float] = {}
    agg_actual_hours: Dict[str, float] = {}

    for inst in plan.task_instances.values():
        active_sec = inst.active_seconds
        if inst.status == TaskStatus.ACTIVE and inst.last_started_ts is not None:
            now = time.time()
            active_sec += max(0.0, now - inst.last_started_ts)

        total_active_seconds += active_sec

        if inst.status == TaskStatus.COMPLETED:
            total_completed_tasks += 1
        if inst.status == TaskStatus.ACTIVE:
            wip_tasks += 1
        if inst.status == TaskStatus.BLOCKED:
            blocked_tasks += 1

        def_id = inst.definition_id
        task_def = plan.tasks[def_id]

        agg_estimated_hours[def_id] = agg_estimated_hours.get(def_id, 0.0) + task_def.estimated_hours
        agg_actual_hours[def_id] = agg_actual_hours.get(def_id, 0.0) + active_sec / 3600.0

    avg_cycle_time_seconds = (
        total_active_seconds / total_completed_tasks
        if total_completed_tasks > 0
        else None
    )

    estimate_vs_actual = {
        def_id: {"estimated": agg_estimated_hours[def_id], "actual": agg_actual_hours[def_id]}
        for def_id in agg_estimated_hours
    }

    return COSExecutionMetrics(
        plan_id=plan.plan_id,
        node_id=plan.node_id,
        total_active_seconds=total_active_seconds,
        total_completed_tasks=total_completed_tasks,
        wip_tasks=wip_tasks,
        blocked_tasks=blocked_tasks,
        avg_cycle_time_seconds=avg_cycle_time_seconds,
        estimate_vs_actual_hours=estimate_vs_actual,
        notes="Execution snapshot from COS Module 4; consumed by COS5/ITC/FRS.",
    )
```

***

**Math Sketch — Cycle Time, WIP, and Deviation**

Let:
- $I$ = set of task instances in the plan
- For each instance $i \in I$:
  - $t_i^{act}$ = actual active time in hours
  - $t_i^{est}$ = estimated hours from its `COSTaskDefinition`

Total actual labor time:

$$
T^{act} = \sum_{i \in I} t_i^{act}
$$

Total estimated labor:

$$
T^{est} = \sum_{i \in I} t_i^{est}
$$

Deviation ratio:

$$
D = \frac{T^{act}}{\max(T^{est}, \epsilon)}
$$

For each task type (definition) $d$:

$$
T_d^{act} = \sum_{i \in I_d} t_i^{act}, \quad
T_d^{est} = \sum_{i \in I_d} t_i^{est}
$$

Little's Law approximation:

Let $\lambda$ = completion rate (tasks per hour) and $WIP$ = number of tasks in ACTIVE + BLOCKED.

$$
CT \approx \frac{WIP}{\lambda}
$$

---
**How Module 4 Talks to ITC, OAD, and FRS**

- **To ITC (Labor Event Capture & Valuation)**
  - COS emits structured labor claims on task completion.
  - ITC Module 1 verifies + records official labor events; Module 2 weights them.
  - Deviations from estimate inform **valuation realism** (true labor intensity).
- **To OAD (Design Feedback)**
  - Chronic overruns or blockages highlight design friction (tooling, alignment, unnecessary steps).
  - OAD redesign reduces cycle time; ITC access-values drop accordingly.
- **To FRS (System Health)**
  - Chronic blocking, over-reliance on individuals, and abnormal overtime patterns become system-health signals.
  - CDS can respond with training programs, safety norms, or redesign directives.

***

**Plain-Language Example**

- Plan: “Wheel truing should take 0.5 hours.”
- Reality: “It’s taking 0.8 hours and blocking often.”
- COS logs it; Module 5 flags a bottleneck; OAD redesign/training improves the workflow; ITC access-values fall as real effort falls.

Module 4 is where that proof lives.

***
