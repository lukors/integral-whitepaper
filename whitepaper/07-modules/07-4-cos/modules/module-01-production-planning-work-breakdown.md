#### Module 1 (COS) — Production Planning & Work Breakdown

**Purpose**
Transform a certified `DesignVersion` + its `OADValuationProfile` into a concrete **COSProductionPlan**: a full work breakdown structure (WBS) with task definitions, expected labor hours by skill tier, expected materials, and an initial cycle-time estimate. This is the first place where **economic calculation becomes an explicit, computable production plan**.

**Role in the system**

- Takes OAD’s **abstract decomposition** (labor steps, BOM, lifecycle hints) and turns it into executable production logic.
- Produces the **expected labor budget** and **material budget** per batch that ITC uses as a *shadow cost* before actual production data arrives.
- Feeds COS Modules 2–5 (labor matching, materials management, workflow execution, bottleneck handling).

**Inputs**

- `DesignVersion` (certified; includes OAD labor-step and BOM data in `parameters`)
- `OADValuationProfile` for that version
- `node_id` (local context)
- `batch_id` and `batch_size` (how many units to produce)
- Optional `node_context` (tooling, workspaces, local cycle-time modifiers)

**Outputs**

- `COSProductionPlan` containing:
  - `COSTaskDefinition`s (template tasks)
  - `COSTaskInstance`s (for this batch)
  - `expected_labor_hours_by_skill`
  - `expected_materials_kg`
  - `expected_cycle_time_hours`
- A simple **plan summary** that ITC can immediately use as an initial (pre-execution) input for valuation.

***

**Assumed OAD Decomposition Format**

We’ll assume OAD includes a decomposition into `version.parameters` like:

```python
version.parameters["labor_steps"] = [
    {
        "id": "frame_weld",
        "name": "Frame Welding",
        "skill_tier": "high",
        "base_hours_per_unit": 1.5,
        "required_tools": ["mig_welder", "frame_jig"],
        "required_workspaces": ["welding_bay_1"],
        "required_materials_kg": {"aluminum_tubing": 3.2, "weld_wire": 0.1},
        "process_eii": 0.45,
        "predecessors": [],
    },
    {
        "id": "wheel_truing",
        "name": "Wheel Truing",
        "skill_tier": "medium",
        "base_hours_per_unit": 1.0,
        "required_tools": ["truing_stand"],
        "required_workspaces": ["wheel_station"],
        "required_materials_kg": {"spokes": 0.6, "rims": 1.2},
        "process_eii": 0.30,
        "predecessors": ["rim_lacing"],
    },
    # ...
]
```

(If upstream OAD uses a different key name than `process_eii`, normalize it here in COS.)

Core Logic — Building the Production Plan

```
import uuid
from datetime import datetime
from typing import Dict, List, Any

# Canonical enums shared with ITC (should match your ITC section)
SkillTier = Literal["low", "medium", "high", "expert"]


def extract_labor_steps_from_oad(version: DesignVersion) -> List[Dict[str, Any]]:
    """
    Extract OAD-provided labor step decomposition from DesignVersion parameters.
    """
    return version.parameters.get("labor_steps", [])


def build_cos_production_plan(
    node_id: str,
    version: DesignVersion,
    oad_profile: OADValuationProfile,
    batch_id: str,
    batch_size: int = 1,
) -> COSProductionPlan:
    """
    COS Module 1 — Production Planning & Work Breakdown
    ---------------------------------------------------
    Transform an OAD-certified DesignVersion into a COSProductionPlan
    with task definitions, task instances, and expected budgets.
    """

    now = datetime.utcnow()
    plan_id = f"plan_{version.id}_{batch_id}"

    labor_steps = extract_labor_steps_from_oad(version)

    tasks_def: Dict[str, COSTaskDefinition] = {}
    tasks_inst: Dict[str, COSTaskInstance] = {}

    expected_labor_hours_by_skill: Dict[SkillTier, float] = {"low": 0.0, "medium": 0.0, "high": 0.0, "expert": 0.0}
    expected_materials_kg: Dict[str, float] = {}

    # --- Create task definitions & instances for the batch ---
    for step in labor_steps:
        task_id = step["id"]
        skill: SkillTier = step["skill_tier"]

        # Normalize optional keys from OAD
        process_eii = step.get("process_eii", step.get("ecological_impact_index", 0.0))

        # Task definition (per unit)
        task_def = COSTaskDefinition(
            id=task_id,
            version_id=version.id,
            name=step["name"],
            description=step.get("description", ""),
            skill_tier=skill,
            estimated_hours_per_unit=step["base_hours_per_unit"],
            required_tools=step.get("required_tools", []),
            required_workspaces=step.get("required_workspaces", []),
            required_materials_kg=step.get("required_materials_kg", {}),
            process_eii=process_eii,
            predecessors=step.get("predecessors", []),
        )
        tasks_def[task_id] = task_def

        # Aggregate expected labor per skill (scaled by batch size)
        expected_labor_hours_by_skill[skill] += task_def.estimated_hours_per_unit * batch_size

        # Aggregate expected materials (scaled by batch size)
        for mat_name, qty_kg in task_def.required_materials_kg.items():
            expected_materials_kg[mat_name] = expected_materials_kg.get(mat_name, 0.0) + (qty_kg * batch_size)

        # Create task instances for this batch
        # Here: one instance per unit for simplicity (can be batch-level later).
        for _ in range(batch_size):
            inst_id = str(uuid.uuid4())
            instance = COSTaskInstance(
                id=inst_id,
                definition_id=task_id,
                batch_id=batch_id,
                node_id=node_id,
                assigned_coop_id=version.parameters.get("default_coop_id", "main_production_coop"),
                status="pending",
                scheduled_start=None,
                scheduled_end=None,
                actual_start=None,
                actual_end=None,
            )
            tasks_inst[inst_id] = instance

    # --- Estimate cycle time (simple heuristic) ---
    # A better version uses critical-path analysis over (predecessors) DAG.
    parallelism_factor = float(version.parameters.get("expected_parallelism_factor", 3.0))
    total_labor_hours = sum(expected_labor_hours_by_skill.values())
    expected_cycle_time_hours = total_labor_hours / max(parallelism_factor, 1.0)

    # Optional: predicted bottlenecks (placeholder heuristic)
    predicted_bottlenecks = version.parameters.get("predicted_bottlenecks", [])

    return COSProductionPlan(
        plan_id=plan_id,
        node_id=node_id,
        version_id=version.id,
        batch_id=batch_id,
        batch_size=batch_size,
        created_at=now,
        tasks=tasks_def,
        task_instances=tasks_inst,
        expected_labor_hours_by_skill=expected_labor_hours_by_skill,
        expected_materials_kg=expected_materials_kg,
        expected_cycle_time_hours=expected_cycle_time_hours,
        predicted_bottlenecks=predicted_bottlenecks,
        notes="Auto-generated from OAD labor decomposition and BOM.",
    )


def summarize_plan_for_itc(plan: COSProductionPlan, oad_profile: OADValuationProfile) -> Dict[str, Any]:
    """
    Provide ITC with an initial 'shadow' valuation basis before execution.
    This summary should reference *canonical* OADValuationProfile fields.
    """
    total_material_mass = sum(plan.expected_materials_kg.values())

    return {
        "version_id": plan.version_id,
        "plan_id": plan.plan_id,
        "batch_id": plan.batch_id,
        "batch_size": plan.batch_size,
        "expected_labor_hours_by_skill": plan.expected_labor_hours_by_skill,
        "expected_materials_kg": plan.expected_materials_kg,
        "expected_cycle_time_hours": plan.expected_cycle_time_hours,
        "total_material_mass_kg": total_material_mass,

        # Canonical OAD valuation fields (names must match your OAD section)
        "oad_embodied_energy_mj": oad_profile.embodied_energy,
        "oad_ecological_score": oad_profile.ecological_score,
        "oad_expected_lifespan_hours": oad_profile.expected_lifespan_hours,
    }
```
**Math Sketch — Labor & Material Budgets**

Let there be a set of labor steps $S = \{ s_1, s_2, \dots, s_n \}$ from OAD.

For each step $s$:
- $h_s$ = base hours per unit
- $k(s)$ = skill tier of step $s$ (e.g. "high", "medium")
- $m_{s,j}$ = kg of material $j$ required per unit

Given batch size $B$:

**1. Expected labor by skill tier**

For each skill tier $\tau$:

$$
H_\tau^{\text{expected}} = \sum_{s \in S \,\mid\, k(s)=\tau} h_s \cdot B
$$

This yields the dictionary value `expected_labor_hours_by_skill[τ]`:

$$
H_\tau^{\text{expected}}
$$

**2. Expected material usage**

For each material $j$:

$$
M_j^{\text{expected}} = \sum_{s \in S} m_{s,j} \cdot B
$$

This yields the dictionary value `expected_materials_kg[j]`:

$$
M_j^{\text{expected}}
$$

**3. Rough expected cycle time**

If we assume an effective parallelism factor $P$ (how many tasks can run concurrently), then:

$$
H_{\text{total}} = \sum_{\tau} H_\tau^{\text{expected}}
$$

A simple heuristic is:

$$
T_{\text{cycle}}^{\text{expected}} \approx \frac{H_{\text{total}}}{\max(P, 1)}
$$

This is crude, but enough for initial planning and ITC shadow valuation; more detailed versions can use full critical-path analysis over the task dependency graph.

***

**Plain-Language Interpretation**

- Module 1 takes OAD's abstract recipe for "how to build one bicycle" and turns it into **specific COS tasks** with hours, skills, tools, and materials for **this node and this batch**.
- It computes:
  - "We expect ~10 expert hours, 25 medium hours, and 15 low-skill hours for this batch."
  - "We will consume ~40 kg of aluminum, 12 kg of rubber, 3 kg of steel," etc.
  - "With our current ability to run tasks in parallel, this batch will take ~X hours."
- ITC now has a **numerical starting point** for the bicycle's eventual access-value—before we even cut the first tube—which will later be corrected by real data from COS Modules 4–5 and FRS.
