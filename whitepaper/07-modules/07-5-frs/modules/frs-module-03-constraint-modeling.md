#### Module 3 (FRS) — Constraint Modeling & System Dynamics Simulation

**Purpose**

Turn `DiagnosticFinding` objects into explicit `ConstraintModel`s and run scenario simulations that map the system’s **viability envelope** across multiple horizons. Module 3 does not compute “optimal plans.” It asks:

> *What is possible, what is fragile, and where are the boundaries of failure if trends persist?*

**Inputs**

- `DiagnosticFinding` objects (from FRS-2)
- Recent `SignalPacket` history (from FRS-1), used to estimate trends and current state
- Optional `MemoryRecord` priors (FRS-6) for baseline parameter ranges (used as priors, not overrides)
- CDS-approved constraint templates and threshold references (FRS reads them; it does not author them)

------

**Outputs**

- A `ConstraintModel` containing:
  - explicit `Constraint` objects (current value, threshold, margin)
  - `ScenarioResult` sets (near/mid/long horizons)
  - breach lists + risk scores
  - trace links back to originating `DiagnosticFinding` IDs
- Optional “scenario narratives” for FRS-5 (derived artifacts; not required)

------

**Core Logic **

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

# ---------------------------------------------------------
# Helpers: constraints + breach + risk scoring
# ---------------------------------------------------------

def build_constraint(
    name: str,
    domain: SignalDomain,
    threshold: float,
    unit: str,
    direction: str,                   # "max" or "min"
    current_value: float,
    tags: List[SemanticTag],
    confidence: Confidence = "medium",
    notes: str = "",
) -> Constraint:
    """
    Construct a Constraint object with computed margin.
    direction="max": current_value must not exceed threshold -> margin = threshold - current_value
    direction="min": current_value must not fall below threshold -> margin = current_value - threshold
    """
    if direction == "max":
        margin = threshold - current_value
    else:  # "min"
        margin = current_value - threshold

    return Constraint(
        name=name,
        domain=domain,
        threshold=threshold,
        unit=unit,
        direction=direction,
        current_value=current_value,
        margin=margin,
        confidence=confidence,
        tags=tags,
        notes=notes,
    )


def is_breached(constraint: Constraint) -> bool:
    """
    Determine whether a constraint is breached.
    """
    if constraint.direction == "max":
        return (constraint.current_value or 0.0) > constraint.threshold
    return (constraint.current_value or 0.0) < constraint.threshold


def risk_from_breaches(breached: List[Constraint], total: List[Constraint]) -> float:
    """
    Simple bounded risk score in [0,1]:
    - breach fraction contributes 60%
    - breach depth contributes 40%
    """
    if not total:
        return 0.0

    frac = len(breached) / len(total)

    depth_terms: List[float] = []
    for c in breached:
        # margin < 0 implies depth; use abs(margin) as depth
        depth = abs(min(c.margin or 0.0, 0.0))
        # crude normalization scale; in production use per-constraint scaling metadata
        scale = 1.0
        depth_terms.append(min(1.0, depth / max(scale, 1e-6)))

    depth_score = sum(depth_terms) / len(depth_terms) if depth_terms else 0.0
    return max(0.0, min(1.0, 0.6 * frac + 0.4 * depth_score))
```

------

**Illustrative Sailboat Model (Toy Parameters Used by the Pseudocode)**

These parameters are only the internal toy-model coefficients used to make the simulation logic concrete; they are not policy, not required structure, and not the only modeling approach.

```python
@dataclass
class SailboatModelParams:
    """
    Illustrative parameters for a sailboat constraint model.
    In practice these would be sector-specific, node-specific,
    and partly learned / bounded by CDS.
    """
    timber_margin_min_kg_week: float = 0.0          # regen - use must be >= 0
    resin_dependency_ratio_max: float = 1.3         # external/internal <= 1.3
    repair_hours_delta_max: float = 0.10            # <= +10% vs baseline

    # Simple illustrative sensitivities (not a required model form)
    humidity_to_repair_sensitivity: float = 0.004
    salinity_to_repair_sensitivity: float = 0.06
    redesign_repair_reduction: float = 0.25
    substitution_resin_reduction: float = 0.40

    demand_growth_default_pct: float = 0.30

    time_step_weeks_near: int = 12
    time_step_weeks_mid: int = 52
    time_step_weeks_long: int = 260
```

------

**Extract current state for modeling**

```python
def extract_sailboat_state(
    current_packet: SignalPacket,
    baseline_packet: Optional[SignalPacket],
) -> Dict[str, float]:
    """
    Extract current state variables for the sailboat context
    from FRS-1 packet metrics (and optional baseline packet).
    """
    inds = compute_sailboat_indicators(current_packet, baseline_packet)

    return {
        "timber_margin_kg_week": inds["timber_margin_kg_week"],                 # regen - use
        "external_internal_resin_ratio": inds["external_internal_resin_ratio"],
        "repair_hours_delta_pct": inds["repair_hours_delta_pct"],               # 0.18 = +18%
        "humidity_pct": inds["humidity_pct"],
        "salinity_index": inds["salinity_index"],
        "timber_use_kg_week": inds["timber_use_kg_week"],
        "timber_regen_kg_week": inds["timber_regen_kg_week"],
    }
```

------

**Convert state into explicit constraints**

```python
def build_sailboat_constraints(
    node_id: str,
    state: Dict[str, float],
    params: SailboatModelParams,
) -> List[Constraint]:
    tags = [SemanticTag("good_id", "sailboat_shared_v1")]

    constraints: List[Constraint] = []

    # C1: Timber sustainability — margin >= 0
    constraints.append(build_constraint(
        name="timber_regeneration_margin",
        domain="ecology",
        threshold=params.timber_margin_min_kg_week,
        unit="kg_week",
        direction="min",
        current_value=state["timber_margin_kg_week"],
        tags=tags + [SemanticTag("material_id", "timber_marine_grade")],
        confidence="medium",
        notes="Timber regen - use should remain non-negative over the long horizon.",
    ))

    # C2: External resin dependency ratio <= max
    constraints.append(build_constraint(
        name="marine_resin_dependency_ratio",
        domain="dependency_autonomy",
        threshold=params.resin_dependency_ratio_max,
        unit="ratio",
        direction="max",
        current_value=state["external_internal_resin_ratio"],
        tags=tags + [SemanticTag("material_id", "marine_resin")],
        confidence="medium",
        notes="External/internal resin ratio bounded to avoid dependency drift.",
    ))

    # C3: Repair labor drift <= max
    constraints.append(build_constraint(
        name="repair_labor_drift",
        domain="quality_reliability",
        threshold=params.repair_hours_delta_max,
        unit="delta_pct",
        direction="max",
        current_value=state["repair_hours_delta_pct"],
        tags=tags,
        confidence="high",
        notes="Repair labor drift should remain under democratically acceptable bounds.",
    ))

    return constraints
```

------

**Scenario projection (illustrative dynamics)**

```python
def project_repair_drift(
    repair_delta: float,
    humidity_pct: float,
    salinity_index: float,
    params: SailboatModelParams,
    redesign: bool,
) -> float:
    baseline_humidity = 70.0
    baseline_salinity = 0.60

    humidity_excess = max(0.0, humidity_pct - baseline_humidity)
    salinity_excess = max(0.0, salinity_index - baseline_salinity)

    next_delta = (
        repair_delta
        + params.humidity_to_repair_sensitivity * humidity_excess
        + params.salinity_to_repair_sensitivity * (salinity_excess / 0.1)
    )

    if redesign:
        next_delta *= (1.0 - params.redesign_repair_reduction)

    return max(0.0, min(1.5, next_delta))


def project_resin_dependency(
    dep_ratio: float,
    demand_growth_pct: float,
    params: SailboatModelParams,
    substitution: bool,
) -> float:
    dep_next = dep_ratio * (1.0 + 0.5 * demand_growth_pct)
    if substitution:
        dep_next *= (1.0 - params.substitution_resin_reduction)
    return max(0.0, dep_next)


def project_timber_margin(
    timber_regen: float,
    timber_use: float,
    demand_growth_pct: float,
    redesign: bool,
) -> float:
    use_next = timber_use * (1.0 + demand_growth_pct)
    if redesign:
        use_next *= 0.85  # illustrative efficiency gain
    return timber_regen - use_next
```

------

**Run scenario suite across horizons**

```python
def run_sailboat_scenarios(
    node_id: str,
    state: Dict[str, float],
    params: SailboatModelParams,
) -> List[ScenarioResult]:

    scenarios = [
        ("S0_status_quo", 0.0, False, False),
        ("S1_demand_growth", params.demand_growth_default_pct, False, False),
        ("S2_redesign", 0.0, True, False),
        ("S3_substitution", 0.0, False, True),
        ("S4_combined", params.demand_growth_default_pct, True, True),
    ]

    horizon_defs = [
        ("near", params.time_step_weeks_near),
        ("mid", params.time_step_weeks_mid),
        ("long", params.time_step_weeks_long),
    ]

    results: List[ScenarioResult] = []

    for scen_id, demand_growth, redesign, substitution in scenarios:
        for horizon, _weeks in horizon_defs:
            repair_delta_proj = project_repair_drift(
                repair_delta=state["repair_hours_delta_pct"],
                humidity_pct=state["humidity_pct"],
                salinity_index=state["salinity_index"],
                params=params,
                redesign=redesign,
            )

            dep_ratio_proj = project_resin_dependency(
                dep_ratio=state["external_internal_resin_ratio"],
                demand_growth_pct=demand_growth,
                params=params,
                substitution=substitution,
            )

            timber_margin_proj = project_timber_margin(
                timber_regen=state["timber_regen_kg_week"],
                timber_use=state["timber_use_kg_week"],
                demand_growth_pct=demand_growth,
                redesign=redesign,
            )

            projected_constraints = build_sailboat_constraints(
                node_id=node_id,
                state={
                    **state,
                    "timber_margin_kg_week": timber_margin_proj,
                    "external_internal_resin_ratio": dep_ratio_proj,
                    "repair_hours_delta_pct": repair_delta_proj,
                },
                params=params,
            )

            breached_constraints = [c for c in projected_constraints if is_breached(c)]
            breach_names = [c.name for c in breached_constraints]
            risk = risk_from_breaches(breached_constraints, projected_constraints)

            results.append(ScenarioResult(
                scenario_id=f"{scen_id}_{horizon}",
                horizon=horizon,  # "near" | "mid" | "long"
                projected_metrics={
                    "repair_hours_delta_pct": repair_delta_proj,
                    "external_internal_resin_ratio": dep_ratio_proj,
                    "timber_margin_kg_week": timber_margin_proj,
                },
                constraint_breaches=breach_names,
                risk_score=risk,
                summary=f"{scen_id} @ {horizon}: breaches={breach_names}, risk={risk:.2f}",
            ))

    return results
```

------

**Main: build a ConstraintModel from Findings + Packets**

```python
def build_constraint_model_from_findings(
    node_id: str,
    current_packet: SignalPacket,
    baseline_packet: Optional[SignalPacket],
    findings: List[DiagnosticFinding],
    params: SailboatModelParams,
) -> ConstraintModel:
    """
    FRS-3: Convert findings into explicit constraints + scenario envelope.
    """
    state = extract_sailboat_state(current_packet, baseline_packet)
    constraints = build_sailboat_constraints(node_id, state, params)

    assumptions = [
        ScenarioAssumption("demand_growth_default_pct", params.demand_growth_default_pct, unit="pct"),
        ScenarioAssumption("redesign_repair_reduction", params.redesign_repair_reduction, unit="fraction"),
        ScenarioAssumption("substitution_resin_reduction", params.substitution_resin_reduction, unit="fraction"),
    ]

    scenario_results = run_sailboat_scenarios(node_id, state, params)

    return ConstraintModel(
        id=generate_id("model"),
        node_id=node_id,
        created_at=datetime.utcnow(),
        constraints=constraints,
        assumptions=assumptions,
        scenario_results=scenario_results,
        related_findings=[f.id for f in findings],
        notes="Constraint model built from FRS-2 findings; scenarios map viability envelope.",
    )
```

------

**Running Example (Sailboat): Findings → Model → Scenario Envelope**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how diagnosed findings are converted into an explicit constraint model and scenario envelope by FRS-3. It introduces no new logic, rules, or authority beyond the formal specification above, and should be read strictly as an informative instantiation of the defined data structures—not as a procedural requirement, execution model, or prescriptive workflow.

```python
params = SailboatModelParams(
    timber_margin_min_kg_week=0.0,
    resin_dependency_ratio_max=1.3,
    repair_hours_delta_max=0.10,
)

model = build_constraint_model_from_findings(
    node_id="node_coastal_A",
    current_packet=current_packet,
    baseline_packet=baseline_packet,
    findings=findings,
    params=params,
)

for r in model.scenario_results:
    if r.constraint_breaches:
        print(r.scenario_id, r.constraint_breaches, r.risk_score)
```

------

**Math Sketches**

**1. Constraint Margin and Breach**

For a "max" constraint $x \le T$:

$$\text{margin} = T - x$$

For a "min" constraint $x \ge T$:

$$\text{margin} = x - T$$

A breach occurs when $\text{margin} < 0$.

**2. Illustrative Repair-Drift Projection**

Let $d$ be repair drift, humidity $H$, salinity $S$:

$$d' = d + a \max(0, H - H_0) + b \max\left(0, \frac{S - S_0}{0.1}\right)$$

If redesign reduces drift by factor $r$:

$$d'' = (1 - r)\, d'$$

**3. Bounded Risk Score from Breaches**

Let $\mathcal{C}$ be constraints, $\mathcal{B}\subseteq \mathcal{C}$ breached:

$$f = \frac{\lvert\mathcal{B}\rvert}{\lvert\mathcal{C}\rvert}$$

where $d$ is a normalized breach-depth term.

---

**Plain-Language Summary**

FRS Module 3 turns "named problems" into **explicit boundaries**:
- it expresses viability as **constraints with margins**,
- explores futures as **scenario envelopes** (not plans),
- and produces structured outputs that FRS-4 can route and FRS-5 can translate—while leaving all authority and choice downstream to CDS and the operational systems.
