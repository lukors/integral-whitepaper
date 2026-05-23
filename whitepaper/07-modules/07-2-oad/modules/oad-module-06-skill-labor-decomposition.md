#### Module 6 (OAD) — Skill & Labor-Step Decomposition

**Purpose**

Convert a certified design version into a computable labor plan: a sequenced set of production and maintenance steps with time estimates, skill tiers, and tooling requirements.

**Role in the system**

This is the bridge from design to economic calculation:

**For COS**, it provides the explicit task graph needed to:

- form cooperatives
- schedule work
- allocate tools and space
- coordinate maintenance cycles

**For ITC**, it provides:

- total labor hours (production + lifecycle maintenance)
- labor broken down by skill tier
- ergonomic and risk flags

Without this module, Integral could not quantify “how much human effort, of what kind, under what conditions” is embodied in a given design.

**Inputs**

- `DesignVersion` (with parameters describing process choices where available)
- Optional `LifecycleModel` (for long-term maintenance planning)
- A process / step template library (standard times and skill assumptions)

**Outputs**

A `LaborProfile` for that `version_id`, containing:

- `production_steps: List[LaborStep]`
- `maintenance_steps: List[LaborStep]`
- `total_production_hours`
- `total_maintenance_hours_over_life`
- `hours_by_skill_tier`
- `ergonomics_flags`, `risk_notes`

These outputs are consumed directly by COS and ITC, and also used to build `OADValuationProfile`.

------

**Core Types**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Literal

SkillTier = Literal["low", "medium", "high", "expert"]

@dataclass
class LaborStep:
    name: str
    estimated_hours: float
    skill_tier: SkillTier
    tools_required: List[str] = field(default_factory=list)
    sequence_index: int = 0
    safety_notes: str = ""
    ergonomics_flags: List[str] = field(default_factory=list)


@dataclass
class LaborProfile:
    version_id: str
    production_steps: List[LaborStep]
    maintenance_steps: List[LaborStep]

    total_production_hours: float
    total_maintenance_hours_over_life: float

    hours_by_skill_tier: Dict[str, float]
    ergonomics_flags: List[str]
    risk_notes: str
```

------

**Core Logic **

1) Process Template Library (Sketch)

```python
from typing import Dict, Any

PROCESS_LIBRARY: Dict[str, Dict[str, Any]] = {
    "cut_frame_members": {
        "base_hours": 1.0,
        "skill_tier": "low",
        "tools": ["saw", "measuring_jig"],
        "ergonomics_flags": ["repetitive_motion"],
        "safety_notes": "Eye/ear protection required.",
    },
    "assemble_housing": {
        "base_hours": 2.0,
        "skill_tier": "medium",
        "tools": ["clamps", "driver"],
        "ergonomics_flags": ["bent_posture"],
        "safety_notes": "Lift assist recommended for heavy parts.",
    },
    "flow_test": {
        "base_hours": 1.0,
        "skill_tier": "medium",
        "tools": ["test_rig"],
        "ergonomics_flags": [],
        "safety_notes": "Pressurized system; check seals.",
    },
    "routine_maintenance": {
        "base_hours": 0.75,
        "skill_tier": "medium",
        "tools": ["basic_hand_tools"],
        "ergonomics_flags": ["awkward_posture"],
        "safety_notes": "Depressurize / power down before opening.",
    },
}
```

------

2) Extract a High-Level Process Plan

```python
from typing import List, Dict, Any

def get_process_plan(version: DesignVersion) -> List[Dict[str, Any]]:
    default_plan = [
        {"task_type": "cut_frame_members", "name": "Cut frame members", "time_multiplier": 1.0},
        {"task_type": "assemble_housing", "name": "Assemble housing", "time_multiplier": 1.0},
        {"task_type": "flow_test", "name": "Run flow test", "time_multiplier": 1.0},
    ]
    return version.parameters.get("process_plan", default_plan)


def get_maintenance_task_def(version: DesignVersion) -> Dict[str, Any]:
    return version.parameters.get("maintenance_task", {
        "task_type": "routine_maintenance",
        "name": "Routine inspection & cleaning",
        "time_multiplier": 1.0,
        "skill_override": None,
    })
```

------

3) Build Production Steps

```python
from typing import List, Dict, Any

def build_production_steps(
    version: DesignVersion,
    process_library: Dict[str, Dict[str, Any]] = PROCESS_LIBRARY,
) -> List[LaborStep]:
    plan = get_process_plan(version)
    labor_steps: List[LaborStep] = []

    for idx, step_def in enumerate(plan):
        task_type = step_def["task_type"]
        tmpl = process_library.get(task_type)

        if tmpl is None:
            base_hours = step_def.get("base_hours", 1.0)
            skill_tier = step_def.get("skill_override", "medium")
            tools = step_def.get("tools", [])
            safety = step_def.get("safety_notes", "Unspecified process; review required.")
            ergonomics = step_def.get("ergonomics_flags", [])
        else:
            base_hours = tmpl["base_hours"]
            skill_tier = step_def.get("skill_override", tmpl["skill_tier"])
            tools = tmpl["tools"]
            safety = tmpl["safety_notes"]
            ergonomics = tmpl.get("ergonomics_flags", [])

        multiplier = step_def.get("time_multiplier", 1.0)
        est_hours = base_hours * multiplier

        labor_steps.append(
            LaborStep(
                name=step_def.get("name", task_type),
                estimated_hours=est_hours,
                skill_tier=skill_tier,
                tools_required=tools,
                sequence_index=idx,
                safety_notes=safety,
                ergonomics_flags=list(ergonomics),
            )
        )

    return labor_steps
```

------

4) Build Maintenance Steps + Compute Lifetime Maintenance Hours

This is where your prior code was inconsistent. We compute total maintenance hours over life using:

- expected lifespan hours (from Module 4)
- maintenance interval days
- labor per maintenance event (from lifecycle model)
- plus the optional task template multiplier

```python
from typing import Optional, Tuple
from math import floor

def build_maintenance_steps_and_totals(
    version: DesignVersion,
    lifecycle: Optional[LifecycleModel],
    process_library: Dict[str, Dict[str, Any]] = PROCESS_LIBRARY,
) -> Tuple[List[LaborStep], float]:
    """
    Returns:
      - a canonical maintenance step (template)
      - total maintenance hours over life (computed from lifecycle model)
    """
    if lifecycle is None or lifecycle.maintenance_interval_days <= 0:
        return [], 0.0

    task_def = get_maintenance_task_def(version)
    task_type = task_def["task_type"]
    tmpl = process_library.get(task_type, {
        "base_hours": lifecycle.maintenance_labor_hours_per_interval,
        "skill_tier": "medium",
        "tools": [],
        "ergonomics_flags": [],
        "safety_notes": "Generic maintenance; review details.",
    })

    multiplier = task_def.get("time_multiplier", 1.0)

    per_event_hours = lifecycle.maintenance_labor_hours_per_interval * multiplier

    # Compute expected lifespan hours from lifecycle.expected_lifetime_years and usage assumptions
    usage = version.parameters.get("usage_assumptions", {"hours_per_day": 4.0, "days_per_year": 250})
    hours_per_year = usage["hours_per_day"] * usage["days_per_year"]
    expected_lifespan_hours = lifecycle.expected_lifetime_years * hours_per_year

    interval_hours = lifecycle.maintenance_interval_days * usage["hours_per_day"]
    num_events = expected_lifespan_hours / max(interval_hours, 1e-6)

    total_maintenance_hours_over_life = num_events * per_event_hours

    step = LaborStep(
        name=task_def.get("name", task_type),
        estimated_hours=per_event_hours,
        skill_tier=task_def.get("skill_override", tmpl["skill_tier"]),
        tools_required=tmpl.get("tools", []),
        sequence_index=0,
        safety_notes=tmpl.get("safety_notes", ""),
        ergonomics_flags=list(tmpl.get("ergonomics_flags", [])),
    )

    return [step], total_maintenance_hours_over_life
```

------

5) Aggregate into a LaborProfile

```python
from typing import List, Dict

def aggregate_hours_by_skill(steps: List[LaborStep]) -> Dict[str, float]:
    agg: Dict[str, float] = {"low": 0.0, "medium": 0.0, "high": 0.0, "expert": 0.0}
    for s in steps:
        agg[s.skill_tier] = agg.get(s.skill_tier, 0.0) + s.estimated_hours
    return agg


def build_labor_profile(
    version: DesignVersion,
    lifecycle: Optional[LifecycleModel] = None,
    process_library: Dict[str, Dict[str, Any]] = PROCESS_LIBRARY,
) -> LaborProfile:
    """
    OAD Module 6 — Skill & Labor-Step Decomposition
    -----------------------------------------------
    Convert a design version + lifecycle model into a LaborProfile
    suitable for COS scheduling and ITC valuation.
    """
    production_steps = build_production_steps(version, process_library)
    maintenance_steps, total_maintenance_hours = build_maintenance_steps_and_totals(
        version, lifecycle, process_library
    )

    total_production_hours = sum(s.estimated_hours for s in production_steps)

    hours_by_skill = aggregate_hours_by_skill(production_steps + maintenance_steps)

    ergonomics_union = sorted(list({
        flag for step in (production_steps + maintenance_steps)
        for flag in step.ergonomics_flags
    }))

    risk_notes = "Review step-level safety_notes and ergonomics_flags for detailed risk profile."

    return LaborProfile(
        version_id=version.id,
        production_steps=production_steps,
        maintenance_steps=maintenance_steps,
        total_production_hours=total_production_hours,
        total_maintenance_hours_over_life=total_maintenance_hours,
        hours_by_skill_tier=hours_by_skill,
        ergonomics_flags=ergonomics_union,
        risk_notes=risk_notes,
    )
```

------

**Math Sketch — Labor Aggregation & Lifetime Effort**

Let:
- $S_p$ = set of production steps
- $S_m$ = set of maintenance steps
- For each step $s$, let $h_s$ = estimated hours and $\tau_s$ = skill tier

Total production hours:

$$H_{\text{prod}} = \sum_{s \in S_p} h_s$$

Total maintenance hours over life (computed from lifecycle interval + lifespan):

$$H_{\text{maint}} = \sum_{s \in S_m} h_s \cdot N_{\text{events}}$$

Total lifetime labor embodied in one unit:

$$H_{\text{total}} = H_{\text{prod}} + H_{\text{maint}}$$

Hours by skill tier $k \in \{\text{low},\text{medium},\text{high},\text{expert}\}$:

$$H_k = \sum_{s:\, \tau_s = k} h_s$$

These values feed directly into ITC access valuation and COS scheduling.
