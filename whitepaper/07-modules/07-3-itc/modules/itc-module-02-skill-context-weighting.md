#### Module 2 (ITC) — Skill & Context Weighting Engine

**Purpose**
Interpret each verified labor event in context—**skill, difficulty, scarcity, ecological sensitivity, urgency**—and convert it into a *weighted* contribution signal that later becomes ITC credit.

**Role in the system**
Module 1 says: *“This work definitely happened and was legitimate.”*
Module 2 says: *“Given what this work was, how demanding it is, and what the system needs right now, how much contribution does it represent?”*

It does this using **CDS-approved weighting policies** (no markets, no bidding, no hidden algorithms). These policies:

- define **base weights** by skill tier and task type
- apply bounded **context modifiers** from COS/FRS (urgency, ecological sensitivity, scarcity)
- clamp all weights within democratic limits (e.g., 0.5–2.0)

The output is a `WeightedLaborRecord` that says, in effect:

> “This 3 hours of medium-skill maintenance on a critical system, during a scarcity window, counts as 4.2 weighted hours of contribution for ITC purposes.”

**Inputs**

- A verified `LaborEvent` (from Module 1)
- A CDS-approved `WeightingPolicy` (active for the node, optionally scoped to a coop or task type)
- Context signals from COS & FRS carried in `LaborEvent.context`

**Outputs**

- A `WeightedLaborRecord`
- A corresponding `LedgerEntry` of type `"labor_weight_applied"`
- *(Optionally, later modules apply `"itc_credited"` to mutate the account balance—kept separate for clarity and auditability.)*

------

**Core Logic **

First, define a policy object consistent with CDS governance:

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

@dataclass
class WeightingPolicy:
    """
    CDS-approved policy controlling how labor gets weighted.
    This is not a market mechanism and not a wage schedule.
    It is a bounded recognition rule-set for contribution signals.
    """
    id: str
    node_id: str
    effective_from: datetime

    # Base weights by skill tier (democratically defined)
    base_weights_by_skill: Dict[SkillTier, float] = field(default_factory=lambda: {
        "low": 1.0, "medium": 1.2, "high": 1.5, "expert": 1.8
    })

    # Optional task-type modifiers (still bounded by global clamps)
    task_type_modifiers: Dict[str, float] = field(default_factory=dict)  # e.g. {"water_testing": 1.1}

    # Context score weights (applied to urgency/ecology/scarcity scores in [-1,+1])
    context_weights: Dict[str, float] = field(default_factory=lambda: {
        "urgency": 0.15,
        "eco_sensitivity": 0.15,
        "scarcity": 0.20,
    })

    # Clamp bounds (democratically bounded ranges)
    context_factor_min: float = 0.70
    context_factor_max: float = 1.50

    min_weight_multiplier: float = 0.50
    max_weight_multiplier: float = 2.00

```

Now the core weighting functions:

```python
from typing import List

WEIGHTING_POLICIES: Dict[str, WeightingPolicy] = {}   # key by node_id (or node_id:coop_id if desired)
WEIGHTED_LABOR: Dict[str, WeightedLaborRecord] = {}   # record_id -> WeightedLaborRecord

def get_weighting_policy(node_id: str, coop_id: Optional[str] = None) -> WeightingPolicy:
    """
    Retrieve the active CDS-approved weighting policy.
    (In practice: resolve by node_id, then optional coop_id override, then federation defaults.)
    """
    if coop_id:
        key = f"{node_id}:{coop_id}"
        if key in WEIGHTING_POLICIES:
            return WEIGHTING_POLICIES[key]
    return WEIGHTING_POLICIES[node_id]


def compute_context_factor(event: LaborEvent, policy: WeightingPolicy) -> float:
    """
    Compute a multiplicative context factor based on urgency, ecological sensitivity,
    and scarcity signals. Scores are expected in [-1, +1] and come from COS/FRS
    (or are precomputed by earlier signal normalization).
    """

    ctx = event.context or {}

    urgency_score = float(ctx.get("urgency_score", 0.0))                 # [-1, +1]
    eco_score = float(ctx.get("eco_sensitivity_score", 0.0))             # [-1, +1]
    scarcity_score = float(ctx.get("scarcity_score", 0.0))               # [-1, +1]

    wu = float(policy.context_weights.get("urgency", 0.0))
    we = float(policy.context_weights.get("eco_sensitivity", 0.0))
    ws = float(policy.context_weights.get("scarcity", 0.0))

    raw = 1.0 + wu * urgency_score + we * eco_score + ws * scarcity_score

    # Clamp within CDS-approved bounds
    return max(policy.context_factor_min, min(policy.context_factor_max, raw))


def get_base_weight(event: LaborEvent, policy: WeightingPolicy) -> float:
    """
    Base weight = skill tier base weight × optional task-type modifier.
    Task type is a metadata label emitted by COS (e.g. "welding", "water_testing").
    """
    skill = event.skill_tier
    task_type = (event.metadata or {}).get("task_type", "generic")

    base_skill = float(policy.base_weights_by_skill.get(skill, 1.0))
    task_mod = float(policy.task_type_modifiers.get(task_type, 1.0))
    return base_skill * task_mod


def weight_labor_event(event: LaborEvent, policy: WeightingPolicy, policy_snapshot_id: str) -> WeightedLaborRecord:
    """
    ITC Module 2 — Skill & Context Weighting Engine
    -----------------------------------------------
    Convert a verified LaborEvent into a WeightedLaborRecord.

    Note: This function does NOT mutate ITCAccount balances.
    Crediting is a separate step (Module 9 orchestration / policy application),
    so weighting cannot be misread as wages or forced incentives.
    """

    base_weight = get_base_weight(event, policy)
    ctx_factor = compute_context_factor(event, policy)

    raw_multiplier = base_weight * ctx_factor

    # Final clamp bounds
    final_multiplier = max(policy.min_weight_multiplier, min(policy.max_weight_multiplier, raw_multiplier))

    weighted_hours = event.hours * final_multiplier

    record_id = generate_id()
    record = WeightedLaborRecord(
        id=record_id,
        event_id=event.id,
        member_id=event.member_id,
        node_id=event.node_id,
        base_hours=event.hours,
        weight_multiplier=final_multiplier,
        weighted_hours=weighted_hours,
        breakdown={
            "base_weight": base_weight,
            "context_factor": ctx_factor,
            "urgency_score": float((event.context or {}).get("urgency_score", 0.0)),
            "eco_sensitivity_score": float((event.context or {}).get("eco_sensitivity_score", 0.0)),
            "scarcity_score": float((event.context or {}).get("scarcity_score", 0.0)),
        },
        created_at=datetime.utcnow(),
    )

    WEIGHTED_LABOR[record_id] = record

    # Ledger entry for auditability (still no balance mutation here)
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=record.created_at,
        entry_type="labor_weight_applied",
        node_id=event.node_id,
        member_id=event.member_id,
        related_ids={
            "event_id": event.id,
            "weighted_record_id": record_id,
            "policy_snapshot_id": policy_snapshot_id,
        },
        details={
            "base_hours": event.hours,
            "weight_multiplier": final_multiplier,
            "weighted_hours": weighted_hours,
            "breakdown": record.breakdown,
        },
    )
    LEDGER[entry.id] = entry

    return record
```

------

**Math Sketch — From Hours to Contribution Signal**

For each valid labor event $e$:
- $h_e$ = raw hours
- $s_e$ = skill tier
- $\text{type}_e$ = task type

Base weight:

$$w_{\text{base}}(e) = w_{\text{skill}}(s_e) \cdot m_{\text{task}}(\text{type}_e)$$

Context scores in $[-1,+1]$:
- $U_e$ = urgency
- $E_e$ = ecological sensitivity
- $S_e$ = scarcity

Context factor:

$$f_{\text{ctx}}(e) = \text{clip}\Big(1 + \alpha_u U_e + \alpha_e E_e + \alpha_s S_e,\; c_{\min},\, c_{\max}\Big)$$

Final multiplier:

$$w_{\text{final}}(e) = \text{clip}\big(w_{\text{base}}(e) \cdot f_{\text{ctx}}(e),\; w_{\min},\, w_{\max}\big)$$

Weighted contribution (in hour-equivalents):

$$C_e = h_e \cdot w_{\text{final}}(e)$$

One hour is not automatically "one unit" of contribution; *contextualized* contribution is what ITC records—without wages, bidding, or markets.

> A verified labor event becomes a *weighted contribution signal* only through **CDS-bounded rules** and **real context signals** (COS/FRS). Weighting does not grant bargaining power; it only produces proportional contribution accounting that later modules may credit.
