#### Module 3 (OAD) — Material & Ecological Coefficient Engine

**Purpose**
Quantify the **ecological and material footprint** of each design version and express it as normalized indices (0–1) plus an aggregate `eco_score` that can be compared across alternatives and used downstream by COS and ITC.

**Role in the system**
This module is the **LCA / sustainability filter** for OAD. It takes a design version and its bill of materials and computes:

- embodied energy and carbon
- toxicity, water use, land use
- recyclability and scarcity indicators

and aggregates them into:

- a detailed `MaterialProfile`
- an `EcoAssessment` with a single `eco_score` and pass/fail flag

These metrics:

- guide designers in OAD (which branches are more sustainable),
- give COS a view of **material intensity**, and
- provide ITC with grounded ecological signals for access valuation.

**Coefficients are not static.**
FRS operational feedback can recalibrate ecological coefficients over time when real-world degradation, scarcity, or ecosystem strain diverges from modeled assumptions.

**Inputs**

- `DesignVersion` (geometry, materials, parameters)
- Bill of materials (material → quantity in kg) extracted from CAD/param tools
- External LCA-style data: per-material coefficients (energy, carbon, toxicity, recyclability, water, land, scarcity)
- Normalization baselines (typical range for that class of design in that sector)
- Optional FRS feedback deltas (regional degradation, scarcity shifts, ecological stress multipliers)

**Outputs**

- `MaterialProfile` for that `version_id` (raw totals + per-material breakdown)
- `EcoAssessment` for that `version_id` (normalized indices + `eco_score`)
- Eco-relevant values that later feed `OADValuationProfile` (e.g., `embodied_energy_mj`, `eco_score`)

***

**Core Logic**

1) Material database (illustrative)

```python
MATERIAL_DB = {
    "steel": {
        "embodied_energy_mj_per_kg": 25.0,
        "carbon_kg_per_kg": 2.5,
        "toxicity_index": 0.3,          # 0–1
        "recyclability_index": 0.8,     # 0–1
        "water_use_l_per_kg": 50.0,
        "land_use_m2_per_kg": 0.02,
        "scarcity_index": 0.4,          # 0–1 (higher = more scarce/constrained)
    },
    # ... more materials
}
```

2) Bill of materials extraction

```python
from typing import Dict, Any, List, Tuple

def extract_bill_of_materials(version: DesignVersion) -> Dict[str, float]:
    """
    Placeholder: in reality, this would parse CAD/geometry data
    to compute a proper bill of materials.
    Returns: {material_name: quantity_kg}
    """
    return version.parameters.get("bill_of_materials_kg", {})
```

3) Build a MaterialProfile from the BOM (including water/land totals + missing material flags)

```python
def build_material_profile(version: DesignVersion) -> Tuple[MaterialProfile, Dict[str, float]]:
    """
    Construct a MaterialProfile from a DesignVersion's BOM and MATERIAL_DB coefficients.
    Returns:
      - MaterialProfile
      - totals: {"water_use_l": ..., "land_use_m2": ..., "missing_materials": [...]}
    """
    bom_kg = extract_bill_of_materials(version)

    total_energy_mj = 0.0
    total_carbon_kg = 0.0
    total_toxicity_mass = 0.0
    total_recyclability_mass = 0.0
    total_scarcity_mass = 0.0
    total_water_l = 0.0
    total_land_m2 = 0.0

    missing_materials: List[str] = []

    total_mass = sum(bom_kg.values()) or 1.0

    for material, qty in bom_kg.items():
        props = MATERIAL_DB.get(material)
        if not props:
            missing_materials.append(material)
            continue

        total_energy_mj += props["embodied_energy_mj_per_kg"] * qty
        total_carbon_kg += props["carbon_kg_per_kg"] * qty
        total_toxicity_mass += props["toxicity_index"] * qty
        total_recyclability_mass += props["recyclability_index"] * qty
        total_scarcity_mass += props.get("scarcity_index", 0.0) * qty
        total_water_l += props.get("water_use_l_per_kg", 0.0) * qty
        total_land_m2 += props.get("land_use_m2_per_kg", 0.0) * qty

    avg_toxicity = total_toxicity_mass / total_mass
    avg_recyclability = total_recyclability_mass / total_mass
    avg_scarcity = total_scarcity_mass / total_mass

    profile = MaterialProfile(
        version_id=version.id,
        materials=list(bom_kg.keys()),
        quantities_kg=bom_kg,
        embodied_energy_mj=total_energy_mj,
        embodied_carbon_kg=total_carbon_kg,
        recyclability_index=avg_recyclability,
        toxicity_index=avg_toxicity,
        scarcity_index=avg_scarcity,
    )

    totals = {
        "water_use_l": total_water_l,
        "land_use_m2": total_land_m2,
        "missing_materials": missing_materials,
    }

    return profile, totals
```

4) Normalization helper

```python
def normalize(value: float, v_min: float, v_max: float) -> float:
    """
    Normalize raw value into [0, 1] given min and max reference points.
    Clamp outside values.
    """
    if v_max == v_min:
        return 0.0
    x = (value - v_min) / (v_max - v_min)
    return max(0.0, min(1.0, x))
```

5) Apply FRS operational feedback (optional recalibration layer)

```python
def apply_frs_eco_adjustments(
    totals: Dict[str, float],
    frs_feedback: Dict[str, Any],
) -> Dict[str, float]:
    """
    Optional: adjust ecological totals using FRS operational feedback.
    Example:
      - regional_water_stress_multiplier
      - regional_land_sensitivity_multiplier
      - scarcity_pressure_multiplier
    """
    water_mult = frs_feedback.get("water_stress_multiplier", 1.0)
    land_mult = frs_feedback.get("land_sensitivity_multiplier", 1.0)

    totals["water_use_l"] *= water_mult
    totals["land_use_m2"] *= land_mult

    return totals
```

6) EcoAssessment computation (policy-configurable threshold)

```python
def compute_eco_assessment(
    version: DesignVersion,
    norm_ref: Dict[str, Dict[str, float]],
    material_profile: MaterialProfile,
    totals: Dict[str, float],
    repairability_hint: float = 0.5,
    eco_threshold: float = 0.5,            # policy-defined
    frs_feedback: Optional[Dict[str, Any]] = None,
) -> EcoAssessment:
    """
    OAD Module 3 — Material & Ecological Coefficient Engine
    -------------------------------------------------------
    Compute normalized eco indices and an aggregate eco_score.

    - Evidence of missing materials should force review downstream.
    - FRS feedback can modulate water/land totals (and later scarcity).
    """
    # Apply FRS adjustments if present
    if frs_feedback:
        totals = apply_frs_eco_adjustments(totals, frs_feedback)

    ee_raw = material_profile.embodied_energy_mj
    carbon_raw = material_profile.embodied_carbon_kg
    tox_raw = material_profile.toxicity_index
    recyc_raw = material_profile.recyclability_index
    water_raw = totals.get("water_use_l", 0.0)
    land_raw = totals.get("land_use_m2", 0.0)

    ee_norm = normalize(ee_raw, norm_ref["embodied_energy_mj"]["min"], norm_ref["embodied_energy_mj"]["max"])
    carbon_norm = normalize(carbon_raw, norm_ref["embodied_carbon_kg"]["min"], norm_ref["embodied_carbon_kg"]["max"])
    tox_norm = normalize(tox_raw, norm_ref["toxicity"]["min"], norm_ref["toxicity"]["max"])
    recyc_norm = normalize(recyc_raw, norm_ref["recyclability"]["min"], norm_ref["recyclability"]["max"])
    water_norm = normalize(water_raw, norm_ref["water_use_l"]["min"], norm_ref["water_use_l"]["max"])
    land_norm = normalize(land_raw, norm_ref["land_use_m2"]["min"], norm_ref["land_use_m2"]["max"])

    # Weights (illustrative; policy-adjustable)
    w_energy = 0.25
    w_carbon = 0.25
    w_toxicity = 0.15
    w_water = 0.15
    w_land = 0.10
    w_recyclability = 0.05
    w_repairability = 0.05

    repair_norm = repairability_hint  # refined in Module 4

    eco_score = (
        w_energy * ee_norm +
        w_carbon * carbon_norm +
        w_toxicity * tox_norm +
        w_water * water_norm +
        w_land * land_norm +
        w_recyclability * (1 - recyc_norm) +
        w_repairability * (1 - repair_norm)
    )

    # Pass/fail includes data completeness gating
    missing = totals.get("missing_materials", [])
    passed = (eco_score <= eco_threshold) and (len(missing) == 0)

    notes = "Auto-computed from MaterialProfile and material database."
    if missing:
        notes += f" Missing materials in DB: {missing}. Requires review."

    return EcoAssessment(
        version_id=version.id,
        embodied_energy_norm=ee_norm,
        carbon_intensity_norm=carbon_norm,
        toxicity_norm=tox_norm,
        recyclability_norm=recyc_norm,
        water_use_norm=water_norm,
        land_use_norm=land_norm,
        repairability_norm=repair_norm,
        eco_score=eco_score,
        passed=passed,
        notes=notes,
    )
```

***

Later, when Module 4 (Lifecycle & Maintainability Modeling) is applied, `repairability_norm` is recalculated using empirically modeled disassembly, maintenance, and refurbishment characteristics, replacing this provisional estimate.

***

**Math Sketch — Eco Score Aggregation**

Let per-design aggregates (from BOM + material coefficients) be:
- $E$ = total embodied energy (MJ)
- $C$ = total embodied carbon (kg CO₂e)
- $T$ = toxicity index (average 0–1)
- $R$ = recyclability index (average 0–1)
- $W$ = total water use (L)
- $L$ = total land use (m²)
- $\rho$ = repairability index (0–1; higher = easier to repair / maintain)

Normalize each dimension:

$$E_n = \text{norm}(E),\quad C_n = \text{norm}(C),\quad T_n = \text{norm}(T),\quad R_n = \text{norm}(R),\quad W_n = \text{norm}(W),\quad L_n = \text{norm}(L),\quad \rho_n = \text{norm}(\rho)$$

with:

$$\text{norm}(X) = \frac{X - X_{\min}}{X_{\max} - X_{\min}} \quad \text{clamped to } [0,1]$$

Define **eco score** as a weighted combination where high energy, carbon, toxicity, water, and land are worse, while higher recyclability and repairability are better:

$$\text{eco score} = w_E E_n + w_C C_n + w_T T_n + w_W W_n + w_L L_n + w_R (1 - R_n) + w_\rho (1 - \rho_n)$$

with:

$$w_E + w_C + w_T + w_W + w_L + w_R + w_\rho = 1$$

A basic pass/fail criterion:

$$\text{passed} = \begin{cases} \text{True}, & \text{if } \text{eco score} \le \tau_{\text{eco}} \\ \text{False}, & \text{otherwise} \end{cases}$$

where $\tau_{\text{eco}}$ is an ecologically conservative threshold chosen per sector.

> The eco score tells us **how damaging a design is per unit of function**, relative to the alternatives. Lower is better. Designs that exceed ecological thresholds are flagged and sent back for redesign instead of being advanced toward production.
