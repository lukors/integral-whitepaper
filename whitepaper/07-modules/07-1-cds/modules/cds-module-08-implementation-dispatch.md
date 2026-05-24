#### Module 8 (CDS) — Implementation Dispatch Interface

**Purpose**

To translate an **approved CDS decision** into **coordinated, system-wide action** by:

- generating actionable tasks
- routing instructions to **COS** (production), **OAD** (design revisions), **ITC** (valuation or weighting updates), and **FRS** (monitoring triggers)
- performing scheduling and resource pre-checks
- ensuring implementation remains aligned with constraints validated in earlier modules
- producing a machine-readable and human-readable **dispatch packet**

This module is the **output port** of CDS: where a decision becomes real-world behavior.

If CDS is the *brain*, Module 8 is the **motor cortex**.

**Inputs**

- `Decision` object with `status = "approved"` (from Module 7)
- `ConsensusResult` with `directive = "approve"` (from Module 6)
- `Scenario` (approved variant)
- `StructuredIssueView` (Module 2, reference only)
- `ContextModel` and `ConstraintReport` (Modules 3–4, reference only)
- Node-wide capacity data from COS (optional lookup)
- Active CDS log chain (Module 7)

**Outputs**

- A `DispatchPacket` defining:
  - cooperative responsibilities
  - task and workflow sequences
  - material and resource requirements
  - scheduling windows
  - OAD follow-up flags
  - ITC weighting / urgency adjustments (if any)
  - FRS monitoring indicators

This packet is then **consumed by COS, OAD, ITC, and FRS**.

***

**Helper Type — DispatchPacket (canonical)**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class DispatchPacket:
    id: str
    issue_id: str
    scenario_id: str
    created_at: datetime

    tasks: List[Dict[str, Any]] = field(default_factory=list)
    materials: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)

    oad_flags: Dict[str, Any] = field(default_factory=dict)
    itc_adjustments: Dict[str, Any] = field(default_factory=dict)
    frs_monitors: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)
```

***

**Core Logic **

```python
from datetime import datetime
from typing import Dict, Any


def generate_dispatch(
    issue: Issue,
    decision: Decision,
    consensus: ConsensusResult,
    scenario: Scenario,
    constraint_report: ConstraintReport,
    cos_capacity_snapshot: Dict[str, Any],
) -> DispatchPacket:
    """
    Module 8 — Implementation Dispatch Interface
    --------------------------------------------
    Translates an approved CDS decision into an actionable
    dispatch packet for COS, OAD, ITC, and FRS.

    Preconditions:
      - decision.status == "approved"
      - consensus.directive == "approve"
      - decision has already been recorded by Module 7
    """
    now = datetime.utcnow()

    assert decision.status == "approved"
    assert consensus.directive == "approve"

    # 1) Extract executable tasks from scenario parameters
    tasks = extract_tasks_from_scenario(scenario)

    # 2) Assign cooperatives based on COS capacity snapshot
    tasks = assign_cooperatives(tasks, cos_capacity_snapshot)

    # 3) Determine material and tooling requirements
    materials = estimate_materials(scenario)

    # 4) Generate scheduling windows (delegated to COS logic)
    schedule = compute_schedule(tasks, cos_capacity_snapshot)

    # 5) OAD follow-up flags (design iteration, certification updates)
    oad_flags = {
        "requires_revision": constraint_report.metadata.get("requires_design_change", False),
        "notes": constraint_report.metadata.get("design_notes", ""),
    }

    # 6) ITC adjustments (only if explicitly required)
    itc_adjustments = {
        "weight_updates": consensus.metadata.get("labor_weight_notes", {}),
        "urgency_factor": scenario.parameters.get("urgency", 1.0),
    }

    # 7) FRS monitoring directives (post-implementation feedback)
    frs_monitors = generate_monitoring_list(scenario)

    dispatch = DispatchPacket(
        id=generate_id("dispatch"),
        issue_id=issue.id,
        scenario_id=scenario.id,
        created_at=now,
        tasks=tasks,
        materials=materials,
        schedule=schedule,
        oad_flags=oad_flags,
        itc_adjustments=itc_adjustments,
        frs_monitors=frs_monitors,
        metadata={
            "decision_id": decision.id,
            "consensus_score": consensus.consensus_score,
            "generated_at": now.isoformat(),
        },
    )

    # Update issue lifecycle state
    issue.status = "dispatched"
    issue.last_updated_at = now

    return dispatch
```

***

**Dispatch Scheduling Logic (Mini-Sketch)**

```python
def compute_schedule(
    tasks: List[Dict[str, Any]],
    cos_capacity_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Example scheduling logic.
    In production systems, COS owns detailed scheduling and optimization.
    """
    earliest_start = datetime.utcnow()
    windows = []

    for t in tasks:
        windows.append({
            "task": t["task"],
            "preferred_window": suggest_window(t["coop"], cos_capacity_snapshot),
        })

    return {
        "earliest_start": earliest_start.isoformat(),
        "windows": windows,
    }
```

***

**Math Sketch — Dependency Ordering**

Tasks are represented as a directed acyclic graph $G = (V, E)$:
- vertices $V$: tasks
- edges $A \rightarrow B$: "A must complete before B begins"

A valid execution order is given by topological sort:

$$\text{Order} = \text{TopoSort}(G)$$

If a cycle exists:

$$\exists (v_1, \dots, v_k) : v_1 \rightarrow \dots \rightarrow v_k \rightarrow v_1$$

Then CDS returns:
- a conflict report
- a revision request (routed back to CDS Modules 4–6 or OAD)

***

**Semantic Summary**

Module 8 ensures that:
- CDS decisions become **coordinated, executable action**
- COS knows *what to do, when, and with what resources*
- OAD knows *whether follow-up design work is required*
- ITC knows *if and how labor weighting or urgency should change*
- FRS knows *what to monitor once implementation begins*

Without Module 8, governance would stall at symbolic agreement. With Module 8, every CDS decision becomes a **full implementation blueprint**, tightly coupled to feedback and review.
