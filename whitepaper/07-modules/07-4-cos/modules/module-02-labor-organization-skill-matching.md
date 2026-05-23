#### Module 2 (COS) — Labor Organization & Skill-Matching

**Purpose**
Match production tasks from the COS production plan to **voluntary participants** based on:

- skill tier and training trajectory
- availability windows
- safety clearances and task hazards
- ITC scarcity/weighting signals

so that production flows smoothly **without managers, wages, or bidding**.

**Role in the system**

- Takes the **COSTaskDefinition/COSTaskInstance** set from Module 1 and the current **person profiles** (CDS identity + skills + safety context, plus COS availability).
- Produces:
  - **recommendation sets** (who is a good fit for what, and why)
  - **demand vs availability** by skill tier
  - **scarcity / surplus indicators** by skill tier (and optionally by task family)
- Feeds:
  - **COS Module 4** (Workflow Execution) with suggested task↔person matches (still voluntary)
  - **ITC Module 2/4** with scarcity indices to inform weighting and training priorities (bounded by CDS)
  - **FRS** with overextension/burnout risk hints and “chronic scarcity” signals

This module **does not assign labor**. It makes the opportunity space legible and helps volunteers find the highest-impact fit.

------

**Key Types**

We assume `COSTaskDefinition`, `COSTaskInstance`, `COSProductionPlan` already exist.

We also assume a `PersonProfile` type exists in CDS/COS identity space; for clarity, COS expects at least:

- `id`, `node_id`
- `primary_skill_tier: SkillTier`
- `skill_tags: List[str]` (optional, for finer matching)
- `training_targets: List[SkillTier]`
- `max_hours_per_window: float`
- `current_committed_hours: float`
- `safety_clearances: List[str]` (e.g., ["welding", "chemicals"])
- `availability_blocks` (optional; time windows)

COS-specific helper types:

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal

SkillTier = Literal["low", "medium", "high", "expert"]

@dataclass
class LaborAvailabilitySnapshot:
    node_id: str
    skill_available_hours: Dict[SkillTier, float]  # tier -> hours available in planning window
    person_ids: List[str]

@dataclass
class LaborDemandSnapshot:
    node_id: str
    skill_required_hours: Dict[SkillTier, float]   # tier -> hours required in plan
    plan_id: str

@dataclass
class TaskAssignmentSuggestion:
    task_instance_id: str
    person_id: str
    score: float
    reason: str

@dataclass
class LaborMatchingResult:
    plan_id: str
    node_id: str
    assignments: List[TaskAssignmentSuggestion]     # suggestions only (not commands)
    demand: LaborDemandSnapshot
    availability: LaborAvailabilitySnapshot
    scarcity_index_by_skill: Dict[SkillTier, float] # >1 scarce, ~1 balanced, <1 surplus
    notes: str
```

------

1. Labor Demand from the Production Plan

```python
def compute_labor_demand_from_plan(plan: COSProductionPlan) -> LaborDemandSnapshot:
    """
    Aggregate required hours by skill tier from the plan.
    Uses task_instances to infer multiplicity (batch size).
    """
    tiers: List[SkillTier] = ["low", "medium", "high", "expert"]
    skill_hours: Dict[SkillTier, float] = {t: 0.0 for t in tiers}

    # Count instances per definition
    inst_count_by_def: Dict[str, int] = {}
    for inst in plan.task_instances.values():
        inst_count_by_def[inst.definition_id] = inst_count_by_def.get(inst.definition_id, 0) + 1

    for def_id, task_def in plan.tasks.items():
        count = inst_count_by_def.get(def_id, 0)
        total_hours = task_def.estimated_hours * count
        # Ensure tier key exists even if custom strings appear
        tier = task_def.skill_tier
        if tier not in skill_hours:
            skill_hours[tier] = 0.0  # type: ignore[assignment]
        skill_hours[tier] += total_hours  # type: ignore[index]

    return LaborDemandSnapshot(
        node_id=plan.node_id,
        skill_required_hours=skill_hours,
        plan_id=plan.plan_id,
    )
```

------

2. Labor Availability from People Profiles

```python
def compute_labor_availability(
    node_id: str,
    people: List["PersonProfile"],
    planning_hours_window: float = 40.0,
) -> LaborAvailabilitySnapshot:
    """
    Estimate available hours by skill tier from voluntary availability declarations.
    (This is a planning snapshot, not a command roster.)
    """
    tiers: List[SkillTier] = ["low", "medium", "high", "expert"]
    skill_avail: Dict[SkillTier, float] = {t: 0.0 for t in tiers}
    person_ids: List[str] = []

    for p in people:
        if p.node_id != node_id:
            continue
        person_ids.append(p.id)

        max_hours = getattr(p, "max_hours_per_window", planning_hours_window)
        committed = getattr(p, "current_committed_hours", 0.0)
        available_hours = max(0.0, max_hours - committed)

        tier = p.primary_skill_tier
        if tier not in skill_avail:
            skill_avail[tier] = 0.0  # type: ignore[assignment]
        skill_avail[tier] += available_hours  # type: ignore[index]

    return LaborAvailabilitySnapshot(
        node_id=node_id,
        skill_available_hours=skill_avail,
        person_ids=person_ids,
    )
```

------

3. Scarcity Index by Skill Tier

```python
def compute_scarcity_index(
    demand: LaborDemandSnapshot,
    availability: LaborAvailabilitySnapshot,
    epsilon: float = 1e-6,
) -> Dict[SkillTier, float]:
    """
    SI_tier = required_hours / max(available_hours, epsilon)
    >1 scarcity, ~1 balanced, <1 surplus.
    """
    scarcity: Dict[SkillTier, float] = {}
    for tier, required in demand.skill_required_hours.items():
        avail = availability.skill_available_hours.get(tier, 0.0)
        scarcity[tier] = required / max(avail, epsilon)
    return scarcity
```

This `scarcity_index_by_skill` is one of the clean signals ITC uses in **Module 2 (weighting)** and **Module 4 (forecasting)**—but COS does not set the weights; it reports the constraint landscape.

------

4. Scoring and Suggesting Matches

Two important upgrades for coherence:

1. **Safety gating first** (no one is suggested for a hazardous task without clearance).
2. **Top-K suggestions** rather than “best single person,” because this is a voluntary system.

Assume `COSTaskDefinition` optionally carries:

- `required_clearances: List[str]` (e.g., ["welding"])
- `hazard_level: float` (0–1) (optional, for risk awareness)

```python
def safety_eligible(person: "PersonProfile", task_def: COSTaskDefinition) -> bool:
    required = getattr(task_def, "required_clearances", [])
    if not required:
        return True
    person_clearances = set(getattr(person, "safety_clearances", []))
    return all(r in person_clearances for r in required)

def score_assignment(
    person: "PersonProfile",
    task_def: COSTaskDefinition,
    scarcity_index_by_skill: Dict[SkillTier, float],
) -> float:
    """
    Advisory scoring heuristic (higher is better).
    """
    score = 0.0

    # 0) Hard safety gate
    if not safety_eligible(person, task_def):
        return float("-inf")

    # 1) Skill fit
    if person.primary_skill_tier == task_def.skill_tier:
        score += 3.0
    elif person.primary_skill_tier in getattr(person, "adjacent_skill_tiers", {}).get(task_def.skill_tier, []):
        score += 2.0
    else:
        score -= 1.0

    # 2) Training trajectory (opt-in learning)
    if task_def.skill_tier in getattr(person, "training_targets", []):
        score += 1.5

    # 3) Scarcity cue (gentle—not coercive)
    si = scarcity_index_by_skill.get(task_def.skill_tier, 1.0)
    if si > 1.0:
        score += min(2.0, (si - 1.0))

    # 4) Avoid overextension
    max_hours = getattr(person, "max_hours_per_window", 40.0)
    committed = getattr(person, "current_committed_hours", 0.0)
    if committed > 0.8 * max_hours:
        score -= 1.5

    return score
```

Now produce recommendations:

```python
def build_labor_matching(
    plan: COSProductionPlan,
    people: List["PersonProfile"],
    top_k: int = 3,
) -> LaborMatchingResult:
    """
    COS Module 2 — Labor Organization & Skill-Matching
    --------------------------------------------------
    Produces *suggestions*, not assignments. UI/workspaces can present
    top_k candidates per task instance, and volunteers self-select.
    """
    demand = compute_labor_demand_from_plan(plan)
    availability = compute_labor_availability(plan.node_id, people)
    scarcity_index = compute_scarcity_index(demand, availability)

    assignments: List[TaskAssignmentSuggestion] = []

    people_by_node = [p for p in people if p.node_id == plan.node_id]

    for inst in plan.task_instances.values():
        if inst.status != "pending":
            continue

        task_def = plan.tasks[inst.definition_id]

        scored: List[tuple[float, "PersonProfile"]] = []
        for p in people_by_node:
            s = score_assignment(p, task_def, scarcity_index)
            if s != float("-inf"):
                scored.append((s, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        for s, p in scored[:top_k]:
            if s <= 0:
                continue
            reason = (
                f"skill_fit={p.primary_skill_tier}→{task_def.skill_tier}; "
                f"training_match={task_def.skill_tier in getattr(p,'training_targets',[]) }; "
                f"scarcity_index={scarcity_index.get(task_def.skill_tier, 1.0):.2f}; "
                f"safety_ok={safety_eligible(p, task_def)}"
            )
            assignments.append(
                TaskAssignmentSuggestion(
                    task_instance_id=inst.id,
                    person_id=p.id,
                    score=s,
                    reason=reason,
                )
            )

    return LaborMatchingResult(
        plan_id=plan.plan_id,
        node_id=plan.node_id,
        assignments=assignments,
        demand=demand,
        availability=availability,
        scarcity_index_by_skill=scarcity_index,
        notes=(
            "Advisory matching suggestions only. Participants self-select tasks; "
            "COS provides visibility, safety gating, and scarcity-aware guidance. "
            "Scarcity indices can be forwarded to ITC (weighting/forecasting) and "
            "to CDS/FRS (training & burnout signals)."
        ),
    )
```

**Important:** These are **suggestions**, not commands. A UI might present:

> “Wheel truing is currently scarce (SI=1.34). You’re eligible and it matches your training goals. Want to take it?”

Voluntary selection remains the rule.

------

**Math Sketch — Demand, Availability, Scarcity, Matching**

Let:
- $\mathcal{T}$ = task definitions
- $\mathcal{I}$ = task instances
- $\mathcal{P}$ = people
- $\Theta$ = skill tiers

**Demand by skill tier**

For each task definition $t$, with $n_t$ instances and $h_t$ hours each, tier $\tau(t)$:

$$
D_\theta = \sum_{t \in \mathcal{T} \mid \tau(t)=\theta} h_t \cdot n_t
$$

**Availability by skill tier**

For each person $p$, available hours $a_p$ and primary tier $\kappa(p)$:

$$
A_\theta = \sum_{p \in \mathcal{P} \mid \kappa(p)=\theta} a_p
$$

**Scarcity index**

$$
SI_\theta = \frac{D_\theta}{\max(A_\theta,\epsilon)}
$$

**Advisory match score**

For person $p$ and instance $i$ (with task definition $t(i)$):

$$
\text{Score}(p,i) =
f_{\text{skill}}(p,t(i)) +
f_{\text{training}}(p,t(i)) +
f_{\text{scarcity}}(\tau(t(i))) +
f_{\text{load}}(p)
$$

subject to a safety constraint:

$$
\text{eligible}(p, t(i)) = 1
$$

The system emits top-$k$ candidates per task instance as **recommendations**, preserving voluntary choice.

---

**Plain-Language Interpretation**

- Module 1 produced a computable plan: "Here's what needs doing, and in what skill tiers."
- Module 2 asks: "Who is available, qualified, and safe to do this—and who wants to learn it?"
- It returns:
  - a scarcity map (where the system is tight), and
  - recommendation sets volunteers can choose from.

COS keeps production flowing without coercion; ITC and CDS get clean signals for weighting, training, and burnout prevention.
