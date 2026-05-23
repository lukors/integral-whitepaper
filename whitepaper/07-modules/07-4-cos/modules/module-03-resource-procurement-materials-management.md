#### Module 3 (COS) — Resource Procurement & Materials Management

**Purpose**
Ensure that all required materials for a production plan are:

- available when needed,
- preferentially sourced from **internal/circular** flows,
- ecologically tracked via **Ecological Impact Indices (EII)**,
- transparently flagged when **transitional external procurement** is required,

and that these results become computable inputs for **ITC valuation**, **OAD redesign**, and **FRS ecological monitoring**.

**Role in the system**
Module 3 sits between **OAD’s design BOM** (as expressed through COS task definitions) and real-world inventories. It:

- allocates internal materials to a plan (respecting reservations and safe floors),
- computes shortfalls and flags what must be procured externally (transitional),
- computes material scarcity indices and aggregate internal/external EII footprints,
- emits clean signals upward to ITC (scarcity/ecology) and laterally to OAD/FRS (substitution + stress).

These outputs feed:

- **ITC** → material scarcity & EII signals as part of access-value computation
- **OAD** → substitution opportunities and design pressure points
- **FRS** → ecological stress, over-extraction risk, import dependency trajectories
- **COS Module 5** → constraints that influence throughput and scheduling

***

Types

This module assumes the COS types already defined earlier, especially:

- `COSProductionPlan`
- `COSTaskDefinition` with `required_materials_kg: Dict[str, float]`
- `COSMaterialStock` (node inventory snapshot)
- `COSMaterialLedgerEntry` (traceable movements)

We define a small, module-local result type to make procurement decisions explicit:

```python
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class MaterialRequirement:
    material_name: str
    required_kg: float
    eii_nominal_per_kg: float  # from OAD/LCA baseline (optional)

@dataclass
class MaterialProcurementDecision:
    material_name: str
    required_kg: float

    allocated_internal_kg: float
    required_external_kg: float

    # EII totals
    eii_internal_total: float
    eii_external_total: float

    # Scarcity signal
    scarcity_index: float               # >1 = scarce, ~1 = balanced, <1 = abundant

    transitional_external_flag: bool
    decision_reason: str

@dataclass
class ResourceProcurementResult:
    plan_id: str
    node_id: str

    requirements: Dict[str, MaterialRequirement]
    decisions: Dict[str, MaterialProcurementDecision]

    stock_after_allocation_kg: Dict[str, float]     # material_name -> remaining usable stock
    aggregate_eii_internal: float
    aggregate_eii_external: float

    data_quality_flags: Dict[str, str]              # material_name -> warning text
    notes: str
```

***

1. Aggregate material requirements from the plan

This version is consistent with COS Module 1’s task schema (`required_materials_kg`).

```python
def compute_material_requirements_from_plan(
    plan: COSProductionPlan,
) -> Dict[str, float]:
    """
    Aggregate total kg required per material across all task instances in this plan.
    """
    total_req: Dict[str, float] = {}

    # Count instances per task definition
    inst_count_by_def: Dict[str, int] = {}
    for inst in plan.task_instances.values():
        inst_count_by_def[inst.definition_id] = inst_count_by_def.get(inst.definition_id, 0) + 1

    for def_id, task_def in plan.tasks.items():
        count = inst_count_by_def.get(def_id, 0)

        for mat_name, kg_per_instance in task_def.required_materials_kg.items():
            total_req[mat_name] = total_req.get(mat_name, 0.0) + kg_per_instance * count

    return total_req
```

***

2. Compute procurement decisions: internal allocation first, then transitional external

We treat **usable internal stock** as:

- `usable = max(0, on_hand_kg - reserved_kg)`

and optionally include `incoming_kg` if policy allows (often discounted as uncertain).

```python
def compute_resource_procurement(
    plan: COSProductionPlan,
    # material_name -> COSMaterialStock
    stock_by_material: Dict[str, COSMaterialStock],
    # material_name -> external EII/kg baseline (if externally procured)
    external_eii_per_kg: Dict[str, float],
    # optional policy knobs
    allow_incoming: bool = True,
    incoming_confidence: float = 0.6,   # how much of incoming_kg we treat as allocatable
) -> ResourceProcurementResult:
    """
    COS Module 3 — Resource Procurement & Materials Management
    ----------------------------------------------------------
    Allocate internal materials first; compute shortfalls; flag transitional external procurement;
    compute scarcity indices and internal/external EII totals.
    """
    required = compute_material_requirements_from_plan(plan)

    decisions: Dict[str, MaterialProcurementDecision] = {}
    requirements: Dict[str, MaterialRequirement] = {}
    data_quality_flags: Dict[str, str] = {}

    stock_after: Dict[str, float] = {}

    agg_eii_int = 0.0
    agg_eii_ext = 0.0

    for mat_name, req_kg in required.items():
        stock = stock_by_material.get(mat_name)

        if stock is None:
            # Unknown material is a *data-quality* problem: OAD/COS must fix BOM metadata.
            data_quality_flags[mat_name] = "Material not found in node stock catalog; treat as external until resolved."
            usable_internal = 0.0
            eii_int_per_kg = 0.0
        else:
            usable_internal = max(0.0, stock.on_hand_kg - stock.reserved_kg)

            if allow_incoming and stock.incoming_kg > 0:
                usable_internal += incoming_confidence * stock.incoming_kg

            # Respect minimum safe stock level (do not allocate below floor)
            usable_internal = max(0.0, usable_internal - stock.min_safe_level_kg)

            eii_int_per_kg = stock.ecological_impact_index

        allocated_internal = min(req_kg, usable_internal)
        external_needed = max(0.0, req_kg - allocated_internal)

        # Scarcity index uses usable_internal *before* allocation (availability pressure)
        denom = max(usable_internal, 1e-6)
        scarcity_index = req_kg / denom if req_kg > 0 else 0.0

        # EII totals
        eii_internal_total = allocated_internal * eii_int_per_kg

        eii_ext_per_kg = external_eii_per_kg.get(mat_name)
        if eii_ext_per_kg is None:
            # If we lack external EII data, flag it (still compute with conservative fallback)
            data_quality_flags.setdefault(mat_name, "Missing external EII/kg baseline; using conservative fallback.")
            eii_ext_per_kg = max(1.2 * eii_int_per_kg, 1.0)

        eii_external_total = external_needed * eii_ext_per_kg

        agg_eii_int += eii_internal_total
        agg_eii_ext += eii_external_total

        transitional_flag = external_needed > 0.0

        # Remaining usable stock (approximate; real system would actually decrement the store)
        remaining_usable = max(0.0, usable_internal - allocated_internal)
        stock_after[mat_name] = remaining_usable

        reason_parts = [
            f"required={req_kg:.2f}kg",
            f"allocated_internal={allocated_internal:.2f}kg",
            f"required_external={external_needed:.2f}kg",
            f"scarcity_index≈{scarcity_index:.2f}",
        ]
        if transitional_flag:
            reason_parts.append("transitional external procurement flagged")

        decisions[mat_name] = MaterialProcurementDecision(
            material_name=mat_name,
            required_kg=req_kg,
            allocated_internal_kg=allocated_internal,
            required_external_kg=external_needed,
            eii_internal_total=eii_internal_total,
            eii_external_total=eii_external_total,
            scarcity_index=scarcity_index,
            transitional_external_flag=transitional_flag,
            decision_reason="; ".join(reason_parts),
        )

        requirements[mat_name] = MaterialRequirement(
            material_name=mat_name,
            required_kg=req_kg,
            eii_nominal_per_kg=eii_int_per_kg if stock else 1.0,
        )

    return ResourceProcurementResult(
        plan_id=plan.plan_id,
        node_id=plan.node_id,
        requirements=requirements,
        decisions=decisions,
        stock_after_allocation_kg=stock_after,
        aggregate_eii_internal=agg_eii_int,
        aggregate_eii_external=agg_eii_ext,
        data_quality_flags=data_quality_flags,
        notes=(
            "Internal/circular allocation prioritized; min-safe floors respected; "
            "incoming stock treated with bounded confidence; external needs flagged as transitional."
        ),
    )
```

**General note:**
If internal procurement is not feasible—because a material, component, or process is currently unavailable within the node—COS flags that portion as **transitional external procurement**. This becomes an explicit prompt for CDS/OAD/FRS.

***

3. Signals to ITC, OAD, and FRS

From `ResourceProcurementResult` we can derive:

- **ITC inputs:** scarcity indices + internal/external EII totals per material and per batch
- **OAD inputs:** repeated high-scarcity materials and high external EII materials as redesign targets
- **FRS inputs:** trends in external dependence, nearing extraction floors, and overall ecological load

***

**Math Sketch — Material Requirements, Scarcity, and EII**

Let:
- $\mathcal{M}$ = set of materials
- $R_m$ = required quantity (kg) of material $m$ for the plan
- $S_m$ = usable internal stock (kg) of material $m$ (after reservations and safe floors)
- $q_m^{int}$ = internal allocation (kg)
- $q_m^{ext}$ = external procurement (kg)
- $e_m^{int}$ = EII per kg for internal/circular supply
- $e_m^{ext}$ = EII per kg for external supply
- $\epsilon > 0$ = small constant

**Allocation**

$$
q_m^{int} = \min(S_m, R_m)
$$

$$
q_m^{ext} = \max(0,\, R_m - S_m)
$$

**Scarcity index**

$$
SI_m = \frac{R_m}{\max(S_m,\epsilon)}
$$

**EII totals**

$$
EII_m^{int} = q_m^{int}\cdot e_m^{int}
$$

$$
EII_m^{ext} = q_m^{ext}\cdot e_m^{ext}
$$

**Aggregate footprint**

$$
EII_{\text{total}}^{int} = \sum_{m\in\mathcal{M}} EII_m^{int}
$$

$$
EII_{\text{total}}^{ext} = \sum_{m\in\mathcal{M}} EII_m^{ext}
$$

---

**Plain-Language Interpretation**

Module 3 is doing four things:
1. "How much of each material does this plan actually need?"
2. "How much can we supply internally (without violating safety floors)?"
3. "What must be procured externally—and how ecologically costly is that?"
4. "Which material constraints should push redesign (OAD), monitoring (FRS), or valuation signals (ITC)?"
