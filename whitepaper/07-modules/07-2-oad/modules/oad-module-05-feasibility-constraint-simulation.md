#### Module 5 (OAD) — Feasibility & Constraint Simulation

**Purpose**

Evaluate whether a design actually works in its intended context: structurally, thermally, hydraulically, and operationally. This module transforms design parameters into **performance indicators, safety margins, manufacturability flags, and an aggregate feasibility score**.

**Role in the system**

If Module 3 (Material & Ecological Coefficients) and Module 4 (Lifecycle & Maintainability) answer *“What does this design cost the world over time?”*, Module 5 answers:

- *Will it break?*
- *Under what loads or flows?*
- *Can it be fabricated with available tools and processes?*
- *Does it meet safety margins under realistic operating conditions?*

Its outputs:

- guide redesign inside OAD,
- inform COS about deployment constraints and risk,
- provide ITC and FRS with **confidence context** (a design that barely survives extreme loads is not equivalent to one with generous safety margins).

This module is where designs stop being conceptual and become **physically accountable**.

**Inputs**

- `DesignVersion` (geometry, materials, parameters)
- Usage & load assumptions (from spec and lifecycle modeling)
- Environmental conditions (temperature, humidity, wind, fluids, corrosion, etc.)
- Manufacturing constraints (tooling envelopes, tolerances, processes)

**Outputs**

A `SimulationResult` object containing:

- per-scenario performance indicators
- an aggregate feasibility score (0–1)
- safety margins (e.g. yield factors)
- manufacturability flags
- detected failure modes

Recall the type:

```python
@dataclass
class SimulationResult:
    version_id: str
    scenarios: Dict[str, Dict]        # scenario_name -> indicators dict
    feasibility_score: float          # 0–1, higher = better
    safety_margins: Dict[str, float]  # e.g. {"yield_factor": 1.5}
    manufacturability_flags: List[str]
    failure_modes: List[str]
```

------

**Core Logic**

**1. Scenario Definition**

```python
from typing import Dict

def build_simulation_scenarios(version: DesignVersion) -> Dict[str, Dict]:
    """
    Construct representative simulation scenarios
    based on expected usage and environment.
    """
    usage = version.parameters.get("usage_assumptions", {
        "hours_per_day": 4.0,
        "days_per_year": 250,
        "design_target_years": 8,
        "environment_stress_factor": 1.0,
    })

    return {
        "nominal_load": {
            "description": "Typical operating load",
            "load_factor": 1.0,
            "env_factor": usage["environment_stress_factor"],
        },
        "peak_load": {
            "description": "Short-duration peak or impact",
            "load_factor": 1.5,
            "env_factor": usage["environment_stress_factor"] * 1.2,
        },
        "extreme_event": {
            "description": "Rare but plausible extreme condition",
            "load_factor": 2.0,
            "env_factor": usage["environment_stress_factor"] * 1.5,
        },
    }
```

------

**2. Simulation Backends (Structural / Flow)**

```python
def run_structural_sim(version: DesignVersion, scenario: Dict) -> Dict:
    """
    Placeholder for structural simulation (FEA-like).
    """
    load_factor = scenario["load_factor"]
    base_stress = version.parameters.get("base_stress_mpa", 50.0)
    yield_strength = version.parameters.get("material_yield_mpa", 250.0)

    max_stress = base_stress * load_factor

    return {
        "max_stress_mpa": max_stress,
        "yield_strength_mpa": yield_strength,
        "stress_ratio": max_stress / yield_strength,
        "max_deflection_mm": 4.0 * load_factor,
    }


def run_flow_sim(version: DesignVersion, scenario: Dict) -> Dict:
    """
    Placeholder for fluid/airflow simulation (CFD-like).
    """
    if not version.parameters.get("fluid_system", False):
        return {}

    base_flow = version.parameters.get("design_flow_lps", 2.0)
    load_factor = scenario["load_factor"]

    return {
        "flow_rate_lps": base_flow * (1.0 - 0.05 * (load_factor - 1.0)),
        "pressure_drop_bar": 0.2 * load_factor,
    }
```

------

**3. Safety & Local Feasibility Scoring**

```python
def compute_safety_and_feasibility(indicators: Dict) -> Dict:
    """
    Convert raw simulation indicators into safety margins
    and a local feasibility score.
    """
    safety_margins = {}
    components = []

    if "stress_ratio" in indicators:
        sr = indicators["stress_ratio"]
        yield_factor = 1.0 / max(sr, 1e-6)
        safety_margins["yield_factor"] = yield_factor

        if sr <= 0.6:
            components.append(1.0)
        elif sr <= 0.9:
            components.append(0.7)
        elif sr <= 1.0:
            components.append(0.4)
        else:
            components.append(0.1)

    if "max_deflection_mm" in indicators:
        md = indicators["max_deflection_mm"]
        components.append(1.0 if md <= 5.0 else 0.6 if md <= 10.0 else 0.3)

    if "flow_rate_lps" in indicators and "pressure_drop_bar" in indicators:
        flow = indicators["flow_rate_lps"]
        dp = indicators["pressure_drop_bar"]
        target = indicators.get("design_flow_target_lps", flow)
        components.append(1.0 if flow >= 0.9 * target and dp <= 0.4 else 0.5)

    local_feasibility = sum(components) / len(components) if components else 0.5

    return {
        "safety_margins": safety_margins,
        "local_feasibility": local_feasibility,
    }
```

------

**4. Aggregate Simulation Result**

```python
def run_feasibility_simulation(version: DesignVersion) -> SimulationResult:
    """
    OAD Module 5 — Feasibility & Constraint Simulation
    """
    scenarios_def = build_simulation_scenarios(version)
    scenario_results = {}
    feasibility_scores = []
    safety_margins_agg = {}
    manufacturability_flags = []
    failure_modes = []

    for name, scenario in scenarios_def.items():
        indicators = {}
        indicators.update(run_structural_sim(version, scenario))
        indicators.update(run_flow_sim(version, scenario))

        if version.parameters.get("fluid_system", False):
            indicators["design_flow_target_lps"] = version.parameters.get(
                "design_flow_lps", 2.0
            )

        safety = compute_safety_and_feasibility(indicators)

        scenario_results[name] = {
            "indicators": indicators,
            "local_feasibility": safety["local_feasibility"],
            "safety_margins": safety["safety_margins"],
        }

        feasibility_scores.append(safety["local_feasibility"])

        for k, v in safety["safety_margins"].items():
            safety_margins_agg.setdefault(k, []).append(v)

        if indicators.get("stress_ratio", 0) > 1.0:
            failure_modes.append(f"{name}: structural yield exceeded")

    safety_margins_final = {
        k: sum(v) / len(v) for k, v in safety_margins_agg.items()
    } if safety_margins_agg else {}

    feasibility_score = (
        sum(feasibility_scores) / len(feasibility_scores)
        if feasibility_scores else 0.5
    )

    if version.parameters.get("requires_5axis_machining", False):
        manufacturability_flags.append("requires_high_end_machining")
    if version.parameters.get("tolerances_microns", 0) > 50:
        manufacturability_flags.append("tight_tolerances")

    return SimulationResult(
        version_id=version.id,
        scenarios=scenario_results,
        feasibility_score=feasibility_score,
        safety_margins=safety_margins_final,
        manufacturability_flags=manufacturability_flags,
        failure_modes=failure_modes,
    )
```

------

**Math Sketch — Feasibility Aggregation**

For scenarios $S = \{s_1, \dots, s_n\}$, each produces a local feasibility score $f_s \in [0,1]$.

Overall feasibility:

$$F = \frac{1}{n} \sum_{s \in S} f_s$$

Safety margins (e.g. yield factor):

$$\text{yield factor}_s = \frac{\sigma_y}{\sigma_{\max}(s)}$$

If any scenario violates safety thresholds (e.g. $\sigma_{\max} > \sigma_y$), the design is flagged with an explicit failure mode and routed back for redesign or risk-aware handling downstream.

---

**Plain-language summary**

> Module 5 answers: *"Does this design survive reality?"*
> It ensures that ecological virtue and lifecycle durability are matched by **physical feasibility, safety margins, and manufacturability**, preventing fragile or idealized designs from advancing unchecked.
