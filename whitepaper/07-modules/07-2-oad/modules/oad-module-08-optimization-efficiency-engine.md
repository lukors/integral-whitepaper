#### Module 8 (OAD) — Optimization & Efficiency Engine

**Purpose**

To algorithmically and participatorily **improve certified-track design variants** by reducing material intensity, ecological burden, labor requirements, failure risk, and maintenance overhead—while increasing durability, modularity, and performance.

**Role in the system**

If Modules 3–7 evaluate *what a design is*, Module 8 actively improves *what it becomes*.

This module:

- transforms **viable designs into preferred designs**,
- explores **multi-objective trade spaces** (ecology vs labor vs performance),
- feeds improved versions directly back into:
  - **COS** (reduced labor & material requirements),
  - **ITC** (lower access cost & long-term burden),
  - **Module 9 Certification** (final gate),
  - **Module 10 Repository** (global propagation).

Optimization here is not profit-seeking or monetary cost minimization. It is:

> **biophysical, labor, lifecycle, and systems optimization for commons utility.**

Module 8 operates **only within the feasible design space** defined by earlier constraint checks (Modules 5 and 7). It does not override safety, ecological, or integration limits—it refines designs *within* them.

**Inputs**

- `DesignVersion` (pre-optimized)
- `EcoAssessment` (Module 3)
- `LifecycleModel` (Module 4)
- `LaborProfile` (Module 6)
- `SimulationResult` (Module 5)
- `IntegrationCheck` (Module 7)
- Material intensity metric (derived from BOM or upstream valuation)

**Outputs**

- `OptimizationResult` object
- A **new optimized `DesignVersion`**
- Updated ecological, labor, lifecycle, and feasibility metrics
- Preferred candidates for **Module 9 Certification**

------

**Reminder: Optimization Result Type**

```python
@dataclass
class OptimizationResult:
    base_version_id: str
    optimized_version_id: str
    objective_value: float
    metrics_before: Dict
    metrics_after: Dict
    improvement_summary: str
```

------

**Core Optimization Logic**

Optimization is **multi-objective**. A single scalar objective is computed from weighted physical and human realities.

------

1. **Extract Optimization Vector**

```python
def extract_optimization_metrics(
    eco: EcoAssessment,
    lifecycle: LifecycleModel,
    labor: LaborProfile,
    sim: SimulationResult,
    integration: IntegrationCheck,
    material_intensity: float,
) -> Dict:
    return {
        "eco_score": eco.eco_score,
        "material_intensity": material_intensity,               # mass-based, not energy
        "production_labor": labor.total_production_hours,
        "maintenance_labor": labor.total_maintenance_hours_over_life,
        "lifecycle_burden": lifecycle.lifecycle_burden_index,   # higher = worse
        "feasibility": sim.feasibility_score,                   # higher = better
        "integration": integration.integration_score,           # higher = better
    }
```

------

2. **Scalar Objective Function**

Lower objective value = **better design**

```py
def compute_objective(metrics: Dict, weights: Dict) -> float:
    """
    Lower objective is better.
    Positive weights = penalties.
    Negative weights = rewards.
    """
    return sum(weights.get(k, 0) * v for k, v in metrics.items())
```

Example Weights

```python
DEFAULT_OPTIMIZATION_WEIGHTS = {
    "eco_score": 0.30,
    "material_intensity": 0.20,
    "production_labor": 0.15,
    "maintenance_labor": 0.15,
    "lifecycle_burden": 0.10,
    "feasibility": -0.05,     # reward
    "integration": -0.05,     # reward
}
```

------

3. **Parameter Mutation Engine (Design Evolution)**

```python
import random

def mutate_design_parameters(
    base_params: Dict,
    mutation_rate: float = 0.1,
) -> Dict:
    new_params = dict(base_params)

    for key, value in base_params.items():
        if isinstance(value, (int, float)) and random.random() < mutation_rate:
            delta = random.uniform(-0.1, 0.1) * value
            new_params[key] = max(0, value + delta)

    return new_params
```

------

4. **Optimization Loop (Evolutionary Sketch)**

```python
def optimize_design(
    base_version: DesignVersion,
    eco: EcoAssessment,
    lifecycle: LifecycleModel,
    labor: LaborProfile,
    sim: SimulationResult,
    integration: IntegrationCheck,
    material_intensity: float,
    iterations: int = 50,
):
    base_metrics = extract_optimization_metrics(
        eco, lifecycle, labor, sim, integration, material_intensity
    )

    best_metrics = dict(base_metrics)
    best_params = dict(base_version.parameters)
    best_objective = compute_objective(
        base_metrics, DEFAULT_OPTIMIZATION_WEIGHTS
    )

    for _ in range(iterations):
        trial_params = mutate_design_parameters(best_params)

        # Re-run upstream evaluators (conceptual)
        trial_eco = simulate_eco(trial_params)
        trial_lifecycle = simulate_lifecycle(trial_params)
        trial_labor = simulate_labor(trial_params)
        trial_sim = simulate_feasibility(trial_params)
        trial_integration = simulate_integration(trial_params)

        trial_metrics = extract_optimization_metrics(
            trial_eco,
            trial_lifecycle,
            trial_labor,
            trial_sim,
            trial_integration,
            material_intensity,
        )

        trial_objective = compute_objective(
            trial_metrics, DEFAULT_OPTIMIZATION_WEIGHTS
        )

        if trial_objective < best_objective:
            best_objective = trial_objective
            best_metrics = trial_metrics
            best_params = trial_params

    optimized_version = DesignVersion(
        id=generate_id(),
        spec_id=base_version.spec_id,
        parent_version_id=base_version.id,
        label=f"{base_version.label}-optimized",
        created_at=datetime.utcnow(),
        authors=base_version.authors,
        cad_files=base_version.cad_files,
        materials=base_version.materials,
        parameters=best_params,
        change_log="Optimized via OAD Module 8.",
        status="optimized",
    )

    return OptimizationResult(
        base_version_id=base_version.id,
        optimized_version_id=optimized_version.id,
        objective_value=best_objective,
        metrics_before=base_metrics,
        metrics_after=best_metrics,
        improvement_summary="Multi-objective physical and labor optimization applied.",
    ), optimized_version
```

------

**Math Sketch — Multi-Objective Optimization**

Let the design state vector be:

$$\mathbf{x} = (E, M, L_p, L_m, B, F, I)$$

Where:
- $E$ = ecological score
- $M$ = material intensity
- $L_p$ = production labor
- $L_m$ = maintenance labor
- $B$ = lifecycle burden
- $F$ = feasibility score
- $I$ = integration score

Define the scalar objective:

$$J(\mathbf{x}) = w_E E + w_M M + w_{Lp} L_p + w_{Lm} L_m + w_B B - w_F F - w_I I$$

Optimization problem:

$$\min_{\mathbf{x} \in \mathcal{D}} J(\mathbf{x})$$

Subject to constraints from:
- Module 5 (safety & feasibility),
- Module 7 (integration),
- ecological thresholds (Module 3).

This is a **Pareto-constrained, multi-objective physical optimization**, not a market cost minimization.

---

**Interpretation in Plain Language**

> Module 8 is where Integral's design intelligence becomes **self-improving**.

It does not ask:
- "What is cheapest?"
- "What is most profitable?"

It asks:
- "What lasts the longest with the least human burden?"
- "What uses the least material and energy for the most service?"
- "What integrates most cleanly into circular infrastructure?"

Designs that survive here become **the backbone of the physical commons**.
