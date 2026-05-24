#### Module 5 (ITC) — Access Allocation & Redemption

**Purpose**
Convert **OAD + COS + FRS** intelligence into a concrete ITC **access obligation** for a good or service, and govern how ITCs are **extinguished** for permanent acquisition (or temporarily **locked** for scarce shared-use access).

This is the formal replacement for price.

**Role in the system**

Everything upstream feeds Module 5:

- **OAD:** design-level labor decomposition, ecology, lifecycle, repairability
- **COS:** real production effort, bottlenecks, throughput, availability
- **FRS:** ecological stress, scarcity shifts, anomaly corrections (failure/maintenance drift), behavioral signals
- **CDS:** normative bounds (fairness classes, caps/floors, essential-goods rules, multiplier bounds)

Module 5:

1. Computes a **base hours-equivalent** access obligation from design + lifecycle + ecology.
2. Applies **bounded context adjustments** (scarcity, eco stress, backlog) using COS/FRS signals.
3. Applies **fairness bounds** (essential caps, luxury floors, etc.) using CDS policy.
4. When access occurs:
   - **Permanent acquisition:** ITCs are **extinguished** (deducted and recorded).
   - **Shared-use:** usually **free**; under scarcity, a temporary **lock** may be applied (deduct → later return).

**Inputs**

For a given `design_version_id` in `node_id`:

- `OADValuationProfile` (design intelligence)
- `LaborProfile` + lifecycle measures (already summarized by OAD profile fields)
- `COSWorkloadSignal` (throughput/backlog/material scarcity)
- `FRSConstraintSignal` (eco pressure + anomaly corrections)
- `CDSPolicySnapshot` (bounds: weight caps, fairness rules, equivalence notes)
- Access context:
  - member `ITCAccount`
  - access mode (`permanent_acquisition`, `shared_use_lock`, `service_use`)
  - item/service identifier (`item_id`)
  - optional local inventory/queue signals from COS (availability/backlog)

**Outputs**

- `AccessValuation` (the computed access obligation with a traceable rationale)
- Updated `ITCAccount` on redemption (balance and totals)
- `RedemptionRecord` (append-only record of extinguishment or lock)
- Corresponding `LedgerEntry` entries:
  - `"access_value_quoted"` and `"access_redeemed"`

***

**Core Logic **

1) Compute the base access obligation

This returns an “hours-equivalent” backbone before context multipliers.

```python
from typing import Dict, Any
from math import tanh

def compute_base_access_obligation_hours(
    oad: OADValuationProfile,
    policy: Dict[str, Any],
) -> float:
    """
    Base hours-equivalent obligation from design intelligence.
    Interprets OAD fields and converts eco/material terms into hours
    using CDS-approved conversion constants.
    """
    # Production labor backbone:
    H_prod = float(oad.estimated_labor_hours)

    # Lifecycle maintenance as hours-equivalent burden per reference service window:
    # If you already carry maintenance labor explicitly in OAD profile, use it here.
    # If not, treat repairability + lifespan as a proxy.
    H_ref = float(policy.get("reference_service_hours", 1000.0))
    H_life = max(float(oad.expected_lifespan_hours), 1e-6)

    # If you have explicit lifetime maintenance hours in OAD, use it:
    H_maint_total = float(policy.get("maintenance_hours_over_life", 0.0))
    # Otherwise approximate from repairability (0–1) and a sector reference
    if H_maint_total <= 0.0:
        maint_reference = float(policy.get("maintenance_reference_hours_over_life", 50.0))
        # lower repairability => higher maintenance
        H_maint_total = maint_reference * (1.0 + (1.0 - float(oad.repairability)))

    H_maint_equiv = (H_maint_total / H_life) * H_ref

    # Eco/material conversion to hours-equivalent:
    energy_to_hours = float(policy.get("energy_to_hours", 0.0))         # hours per MJ
    eco_score_to_hours = float(policy.get("eco_score_to_hours", 0.0))   # hours per normalized eco score
    mat_to_hours = float(policy.get("mat_intensity_to_hours", 0.0))     # hours per unit material intensity

    H_eco = (
        float(oad.embodied_energy) * energy_to_hours
        + float(oad.ecological_score) * eco_score_to_hours
    )

    H_mat = float(oad.material_intensity) * mat_to_hours

    # Optional weights (bounded by CDS policy)
    w_eco = float(policy.get("eco_weight", 0.2))
    w_mat = float(policy.get("scarcity_weight_design", 0.2))

    base_hours = H_prod + H_maint_equiv + w_eco * H_eco + w_mat * H_mat

    # Never below zero
    return max(0.0, base_hours)
```

2) Compute bounded context multipliers

```python
def compute_context_multipliers(
    cos: COSWorkloadSignal,
    frs: FRSConstraintSignal,
    policy: Dict[str, Any],
) -> Dict[str, float]:
    """
    Produce bounded multipliers tied to reality (not speculation).
    """
    # Inputs (normalized or semi-normalized indices)
    # - scarcity should be derived from COS material indices and FRS material pressure
    scarcity_index = float(policy.get("scarcity_index", 0.0))
    backlog_index = float(policy.get("backlog_index", 0.0))

    # Use FRS eco pressure directly as an "eco-stress index"
    eco_stress_index = float(frs.eco_pressure_index)

    # Bounds
    max_scarcity_boost = float(policy.get("max_scarcity_boost", 0.5))
    max_eco_boost = float(policy.get("max_eco_boost", 0.5))
    max_backlog_boost = float(policy.get("max_backlog_boost", 0.3))
    max_relief = float(policy.get("max_relief", 0.3))

    scarcity_m = 1.0 + max_scarcity_boost * tanh(scarcity_index)
    eco_m      = 1.0 + max_eco_boost * tanh(eco_stress_index)
    backlog_m  = 1.0 + max_backlog_boost * tanh(backlog_index)

    scarcity_m = max(1.0 - max_relief, min(1.0 + max_scarcity_boost, scarcity_m))
    eco_m      = max(1.0 - max_relief, min(1.0 + max_eco_boost, eco_m))
    backlog_m  = max(1.0 - max_relief, min(1.0 + max_backlog_boost, backlog_m))

    return {
        "scarcity_multiplier": scarcity_m,
        "eco_stress_multiplier": eco_m,
        "backlog_multiplier": backlog_m,
    }
```

> **Note:** In production, you’d compute `scarcity_index` and `backlog_index` from COS availability/backlog metrics, and incorporate `frs.material_pressure_index` where relevant. I left them as policy-fed placeholders because your earlier sections treat those as already available aggregates.

3) Apply fairness class bounds (CDS policy)

```python
def apply_fairness_bounds(
    raw_itc: float,
    fairness_class: str,
    policy: Dict[str, Any],
) -> float:
    rules = policy.get("fairness_classes", {}).get(fairness_class, {})
    min_itc = float(rules.get("min_credits", 0.0))
    max_itc = float(rules.get("max_credits", float("inf")))
    return max(min_itc, min(raw_itc, max_itc))
```

4) Put it together: compute an `AccessValuation`

```python
def compute_access_valuation(
    item_id: str,
    design_version_id: str,
    node_id: str,
    oad: OADValuationProfile,
    cos: COSWorkloadSignal,
    frs: FRSConstraintSignal,
    policy: Dict[str, Any],
    policy_snapshot_id: str,
    fairness_class: str = "standard",
) -> AccessValuation:
    """
    Compute the full access obligation (NOT a price).
    """
    base_hours = compute_base_access_obligation_hours(oad, policy)

    multipliers = compute_context_multipliers(cos, frs, policy)
    scarcity_m = multipliers["scarcity_multiplier"]
    eco_m = multipliers["eco_stress_multiplier"]
    backlog_m = multipliers["backlog_multiplier"]

    raw_hours = base_hours * scarcity_m * eco_m * backlog_m

    # Convert hours-equivalent to ITCs (often 1:1, but bounded by CDS policy)
    hours_to_itc = float(policy.get("hours_to_itc", 1.0))
    raw_itc = raw_hours * hours_to_itc

    final_itc = apply_fairness_bounds(raw_itc, fairness_class, policy)

    # Build hours-equivalent adjustments for transparency (optional)
    eco_adj = base_hours * (eco_m - 1.0)
    scarcity_adj = base_hours * (scarcity_m - 1.0)
    backlog_adj = base_hours * (backlog_m - 1.0)

    return AccessValuation(
        item_id=item_id,
        design_version_id=design_version_id,
        node_id=node_id,
        base_weighted_labor_hours=base_hours,      # here used as “base hours-equivalent”
        eco_burden_adjustment=eco_adj,
        material_scarcity_adjustment=scarcity_adj,
        repairability_credit=0.0,                  # already folded into base in this sketch
        longevity_credit=0.0,                      # already folded into base in this sketch
        final_itc_cost=final_itc,
        computed_at=datetime.utcnow(),
        valid_until=None,
        policy_snapshot_id=policy_snapshot_id,
        rationale={
            "base_hours_equiv": base_hours,
            "scarcity_multiplier": scarcity_m,
            "eco_stress_multiplier": eco_m,
            "backlog_multiplier": backlog_m,
            "raw_itc": raw_itc,
            "final_itc": final_itc,
            "fairness_class": fairness_class,
        },
    )
```

5) Redemption: permanent extinguishment vs shared-use lock

This uses your canonical `RedemptionRecord` and `LedgerEntry`.

```python
def redeem_access(
    account: ITCAccount,
    valuation: AccessValuation,
    mode: AccessMode,
    lock_expires_at: Optional[datetime] = None,
) -> RedemptionRecord:
    """
    Apply the access outcome to the member account and return a RedemptionRecord.
    - permanent_acquisition: ITCs extinguished (deducted).
    - shared_use_lock: ITCs temporarily locked (deduct now; restore on return).
    - service_use: may be zero or small; system-defined.
    """

    cost = float(valuation.final_itc_cost)

    # Shared-use is often free; enforce policy elsewhere by passing cost=0.
    if cost > 0 and account.balance < cost:
        raise ValueError("insufficient ITC balance")

    if mode == "permanent_acquisition":
        account.balance -= cost
        account.total_redeemed += cost

    elif mode == "shared_use_lock":
        # Lock behaves like a refundable hold.
        # Implementation detail: you may want a separate Lock table.
        account.balance -= cost

    elif mode == "service_use":
        account.balance -= cost
        account.total_redeemed += cost

    rec = RedemptionRecord(
        id=generate_id(),
        member_id=account.member_id,
        node_id=account.node_id,
        item_id=valuation.item_id,
        itc_spent=cost,
        redemption_time=datetime.utcnow(),
        redemption_type=mode,
        expires_at=lock_expires_at,
        access_valuation_snapshot=valuation,
    )

    # Ledger entry (append-only)
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=rec.redemption_time,
        entry_type="access_redeemed",
        node_id=account.node_id,
        member_id=account.member_id,
        related_ids={
            "redemption_id": rec.id,
            "item_id": valuation.item_id,
            "design_version_id": valuation.design_version_id,
        },
        details={
            "mode": mode,
            "itc_spent": cost,
            "balance_after": account.balance,
            "policy_snapshot_id": valuation.policy_snapshot_id,
            "rationale": valuation.rationale,
        },
    )
    # append_ledger_entry(entry)  # use your ledger append function
    return rec
```

> If you want the **lock return** logic documented: on return, you’d create a ledger entry that restores `account.balance += lock_amount` and records `"shared_use_lock_released"` (you can add it as a ledger entry type if desired).

***

**Math Sketch — Formal Access-Value Computation**

Let a good $g$ with design version $v$ in node $n$.

**Base hours-equivalent obligation** (design-level):

$$H_{\text{base}} = H_{\text{prod}} + \frac{H_{\text{maint,total}}}{H_{\text{life}}}\,H_{\text{ref}} + w_E(\alpha_E E + \alpha_S S_{\text{eco}}) + w_M(\alpha_M M)$$

**Context multipliers** (bounded, smooth):

$$m_{\text{sc}} = 1 + B_{\text{sc}} \tanh(\sigma_{\text{sc}})$$

$$m_{\text{eco}} = 1 + B_{\text{eco}} \tanh(\sigma_{\text{eco}})$$

$$m_{\text{back}} = 1 + B_{\text{back}} \tanh(\sigma_{\text{back}})$$

**Raw ITC obligation**:

$$C_{\text{raw}} = \beta \, H_{\text{base}} \, m_{\text{sc}} \, m_{\text{eco}} \, m_{\text{back}}$$

**Fairness bounds** by class $f$:

$$C_{\text{final}} = \min\Big(\max(C_{\text{raw}}, C_{f,\min}), \; C_{f,\max}\Big)$$
