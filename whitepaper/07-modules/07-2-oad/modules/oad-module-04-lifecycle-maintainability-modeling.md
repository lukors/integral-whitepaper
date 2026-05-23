#### Module 4 (OAD) — Lifecycle & Maintainability Modeling

**Purpose**

Estimate how a design behaves over time: how long it lasts, how often it fails, how much maintenance labor it demands, and how repairable it is. This transforms a static design into a **time-profile of labor, risk, and service capacity**.

**Role in the system**

This module connects OAD to COS and ITC at the **temporal** level. Two designs may have similar build-time ecological footprints but radically different:

- lifespans
- failure rates
- maintenance burdens
- downtime profiles

Lifecycle modeling converts those differences into computable signals for:

- **COS** — planning long-term maintenance cooperatives and labor flows
- **ITC** — valuing goods in a way that rewards durability and repairability (lower access cost per unit of service for robust designs)
- **FRS** — benchmarking real-world performance against design expectations

> **Module 4 is the authoritative source of repairability and maintenance metrics.**
>  Any provisional repairability estimates from Module 3 are superseded here by empirically modeled maintenance and disassembly characteristics.

**Inputs**

- `DesignVersion` (geometry, parameters, environmental context)
- Usage assumptions (e.g. cycles per day, days per year, stress factors)
- `EcoAssessment` (especially recyclability and toxicity signals)
- Optional empirical data from similar designs or prior deployments

**Outputs**

- A `LifecycleModel` for the given `version_id`
- Derived values including:
  - expected lifespan (hours / years)
  - maintenance labor over lifecycle
  - maintenance event frequency
  - repairability index (0–1)
  - downtime fraction over lifespan

These outputs later populate the **`OADValuationProfile`** consumed by COS and ITC.

***

**Lifecycle Model Type**

```python
from dataclasses import dataclass
from typing import List

@dataclass
class LifecycleModel:
    """
    Expected lifetime behavior of the design, including maintenance burden.
    """
    version_id: str
    expected_lifetime_years: float
    maintenance_events_expected: float
    maintenance_interval_days: float
    maintenance_labor_hours_per_interval: float
    disassembly_hours: float
    refurb_cycles_possible: int
    dominant_failure_modes: List[str]

    lifecycle_burden_index: float  # 0–1, higher = more labor / risk over time
```

***

**Core Logic**

1. Usage assumptions

```python
from typing import Dict

def get_usage_assumptions(version: DesignVersion) -> Dict:
    """
    Extract nominal usage pattern from parameters or metadata.

    Example:
    {
      "hours_per_day": 6.0,
      "days_per_year": 300,
      "design_target_years": 10,
      "environment_stress_factor": 1.0
    }
    """
    return version.parameters.get("usage_assumptions", {
        "hours_per_day": 4.0,
        "days_per_year": 250,
        "design_target_years": 8,
        "environment_stress_factor": 1.0,
    })
```

***

2. Reliability estimate (MTTF)

```python
def estimate_mttf_hours(
    base_hours: float,
    stress_factor: float,
    material_factor: float,
) -> float:
    """
    Estimate mean time to failure (MTTF).

    - base_hours: nominal rating
    - stress_factor: >1 increases failure risk
    - material_factor: >1 improves robustness
    """
    return base_hours * material_factor / max(stress_factor, 0.1)
```

***

3. Maintenance labor estimation

```python
def estimate_maintenance_labor(
    lifespan_hours: float,
    maintenance_interval_hours: float,
    labor_per_event_hours: float,
) -> float:
    """
    Approximate total maintenance labor over the design lifespan.
    """
    if maintenance_interval_hours <= 0:
        return 0.0

    expected_events = lifespan_hours / maintenance_interval_hours
    return expected_events * labor_per_event_hours
```

***

4. Lifecycle computation

```python
def compute_lifecycle_model(
    version: DesignVersion,
    eco_assessment: EcoAssessment,
    base_mttf_hours: float = 20000.0,
    base_maintenance_interval_hours: float = 2000.0,
    labor_per_maintenance_event_hours: float = 2.0,
    refurb_cycles_possible: int = 2,
) -> LifecycleModel:
    """
    OAD Module 4 — Lifecycle & Maintainability Modeling
    ---------------------------------------------------
    Compute expected lifetime behavior, maintenance labor,
    repairability, and downtime signals.
    """

    usage = get_usage_assumptions(version)
    hours_per_year = usage["hours_per_day"] * usage["days_per_year"]
    design_years = usage["design_target_years"]
    stress_factor = usage["environment_stress_factor"]

    # Material robustness proxy
    material_factor = (
        0.5 * eco_assessment.recyclability_norm +
        0.5 * (1.0 - eco_assessment.toxicity_norm)
    )

    mttf_hours = estimate_mttf_hours(
        base_hours=base_mttf_hours,
        stress_factor=stress_factor,
        material_factor=material_factor,
    )

    raw_lifespan_hours = design_years * hours_per_year
    expected_lifespan_hours = min(raw_lifespan_hours, mttf_hours * 1.5)

    maintenance_interval_hours = base_maintenance_interval_hours * (
        mttf_hours / base_mttf_hours
    )

    maintenance_labor_total = estimate_maintenance_labor(
        lifespan_hours=expected_lifespan_hours,
        maintenance_interval_hours=maintenance_interval_hours,
        labor_per_event_hours=labor_per_maintenance_event_hours,
    )

    maintenance_events_expected = (
        expected_lifespan_hours / maintenance_interval_hours
        if maintenance_interval_hours > 0 else 0
    )

    # Repairability & downtime
    if maintenance_events_expected == 0:
        repairability_index = 1.0
        downtime_fraction = 0.0
    else:
        avg_labor_per_event = maintenance_labor_total / maintenance_events_expected
        repairability_index = 1.0 / (1.0 + avg_labor_per_event / 4.0)
        downtime_fraction = min(0.3, maintenance_events_expected * 0.002)

    # Lifecycle burden index
    labor_norm = min(1.0, maintenance_labor_total / 500.0)
    downtime_norm = min(1.0, downtime_fraction / 0.3)
    lifecycle_burden_index = 0.6 * labor_norm + 0.4 * downtime_norm

    return LifecycleModel(
        version_id=version.id,
        expected_lifetime_years=expected_lifespan_hours / max(hours_per_year, 1.0),
        maintenance_events_expected=maintenance_events_expected,
        maintenance_interval_days=maintenance_interval_hours / max(usage["hours_per_day"], 0.1),
        maintenance_labor_hours_per_interval=labor_per_maintenance_event_hours,
        disassembly_hours=version.parameters.get("disassembly_hours", 1.0),
        refurb_cycles_possible=refurb_cycles_possible,
        dominant_failure_modes=version.parameters.get("failure_modes", []),
        lifecycle_burden_index=lifecycle_burden_index,
    )
```

***

**Linking to OADValuationProfile (OAD → COS & ITC)**

```python
def build_valuation_profile_from_oad(
    version: DesignVersion,
    material_profile: MaterialProfile,
    eco: EcoAssessment,
    lifecycle: LifecycleModel,
) -> OADValuationProfile:
    """
    Condense OAD outputs into a single valuation profile for COS & ITC.
    """

    total_material_mass = sum(material_profile.quantities_kg.values())

    usage = get_usage_assumptions(version)
    hours_per_year = usage["hours_per_day"] * usage["days_per_year"]
    expected_lifespan_hours = lifecycle.expected_lifetime_years * hours_per_year

    maintenance_labor_hours_over_life = (
        lifecycle.lifecycle_burden_index * 500.0
    )

    return OADValuationProfile(
        version_id=version.id,
        material_intensity=total_material_mass,
        ecological_score=eco.eco_score,
        bill_of_materials=material_profile.quantities_kg,
        embodied_energy=material_profile.embodied_energy_mj,
        embodied_carbon=material_profile.embodied_carbon_kg,
        expected_lifespan_hours=expected_lifespan_hours,
        production_labor_hours=sum(
            step.estimated_hours for step in version.parameters.get("production_steps", [])
        ),
        maintenance_labor_hours_over_life=maintenance_labor_hours_over_life,
        hours_by_skill_tier=version.parameters.get("hours_by_skill_tier", {}),
        notes="Auto-generated OAD valuation profile from Modules 3–4.",
    )
```

***

**Math Sketch — Lifecycle Labor & Repairability**

Let:
- $H_{\text{life}}$ = expected lifespan (hours)
- $I_{\text{maint}}$ = maintenance interval (hours)
- $h_{\text{event}}$ = labor hours per maintenance event

Then:

$$N_{\text{events}} = \frac{H_{\text{life}}}{I_{\text{maint}}}$$

Average labor per event:

$$\bar{h} = \frac{L_{\text{total}}}{N_{\text{events}}}$$

Define repairability index:

$$R_{\text{rep}} = \frac{1}{1 + \bar{h} / H_0}$$

Lifecycle burden:

$$B_{\text{life}} = \alpha \cdot \text{norm}(L_{\text{total}}) + (1 - \alpha) \cdot \text{norm}(\text{downtime})$$

From ITC's perspective:
- Higher $B_{\text{life}}$ → higher access-value per unit of service
- Lower $B_{\text{life}}$ → durable, low-maintenance designs → lower access-value
