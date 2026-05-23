#### Module 9 (ITC) — Integration & Coordination

Purpose

Synchronize ITC with the full Integral stack—**CDS** (policy), **OAD** (design intelligence), **COS** (real workloads), and **FRS** (feedback)—so that:

- weighting bands, scarcity coefficients, and access-valuation parameters
- cross-node equivalence interpretation bands
- and fairness / ethics guardrails

are **continuously recalibrated in response to real-world conditions**, but **only within democratically approved bounds**.

This is the *cybernetic glue* that keeps ITC adaptive without turning it into an autonomous “policy authority.”

***

Role in the System

Module 9 performs four functions:

1. **Collects signals**
   - from **OAD**: updated valuation profiles (labor, lifecycle, eco, scarcity)
   - from **COS**: demand/supply ratios, backlogs, bottlenecks, throughput constraints
   - from **FRS**: ecological pressure, fairness anomalies, proto-market risk indicators
   - from **CDS**: current policy snapshots and hard bounds
2. **Generates bounded adjustment proposals**
   - small nudges to weight bands for scarce skill tiers
   - small nudges to scarcity coefficients for stressed materials
   - **decay-rule selection** (choose among CDS-approved `DecayRule` IDs; no hidden decay rate)
   - cross-node equivalence band refresh (interpretation at access time)
3. **Routes proposals through CDS**
   - no “self-updates” behind the scenes
   - CDS can approve, amend, or reject the proposed adjustments
4. **Activates a new ITC policy snapshot and logs it**
   - updates the active policy used by Modules 1–8
   - writes a `policy_updated` entry to the ITC ledger (Module 8) for traceability

***

**Core Types:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Any
from datetime import datetime

SkillTier = Literal["low", "medium", "high", "expert"]

@dataclass
class WeightingBand:
    """
    CDS-bounded base multipliers per skill tier (can be node-specific).
    """
    skill_tier: SkillTier
    base_multiplier: float

@dataclass
class ITCPolicySnapshot:
    """
    Runtime policy snapshot consumed by Modules 1–8.
    This is *derived from* CDS decisions (not authored by ITC).
    """
    id: str
    node_id: str
    effective_from: datetime
    cds_policy_snapshot_id: str                     # link back to CDS authority
    active_decay_rule_id: str                       # must be one of CDS-approved decay rules

    # Bounded parameters used in weighting/valuation:
    weight_bands: Dict[SkillTier, WeightingBand] = field(default_factory=dict)
    scarcity_coeffs: Dict[str, float] = field(default_factory=dict)  # material -> coefficient

    # Cross-node interpretation bands used at access computation time:
    equivalence_bands: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # e.g. { "home->local": {"labor_context_factor":1.05, "eco_context_factor":0.98} }

    notes: str = ""
    created_from_proposal_id: Optional[str] = None


@dataclass
class PolicyProposal:
    """
    Proposed adjustment to ITC policy parameters (must be CDS-reviewed).
    """
    id: str
    created_at: datetime
    node_id: str
    changes: Dict[str, Any]            # {"weight_bands":..., "scarcity_coeffs":..., "active_decay_rule_id":...}
    rationale: str
    generated_by: str                  # "automatic" or committee id
```

***

**Signal Aggregation**

```python
def collect_latest_signals(node_id: str) -> Dict[str, Any]:
    """
    Gather current OAD, COS, FRS, and CDS signals relevant for ITC coordination.
    In a real system, this would query services or caches.
    """
    oad_payloads = fetch_oad_summaries(node_id)       # design valuation snapshots
    cos_signal   = fetch_cos_demand(node_id)          # demand/supply + backlogs
    frs_signal   = fetch_frs_feedback(node_id)        # eco stress + anomalies
    cds_policy   = fetch_cds_policy_snapshot(node_id) # bounds + allowed decay rules

    return {"oad": oad_payloads, "cos": cos_signal, "frs": frs_signal, "cds": cds_policy}
```

***

**Policy Adjustment Heuristics**

Key principle: **Module 9 proposes; CDS disposes.**

```python
from math import tanh

def choose_decay_rule_id(
    current_decay_rule_id: str,
    allowed_decay_rule_ids: List[str],
    frs_proto_market_risk: float,
    frs_participation_index: float,
) -> str:
    """
    Select among CDS-approved decay rules (no hidden decay rate).
    Heuristic sketch:
    - if proto-market risk is high -> prefer 'faster' decay rule (if available)
    - if participation is low and risk is low -> prefer 'gentler' decay rule (if available)
    - otherwise keep current
    """
    if not allowed_decay_rule_ids:
        return current_decay_rule_id

    # Convention: CDS can label decay rules in metadata; here we just assume helper selectors exist.
    faster = pick_decay_rule_by_tag(allowed_decay_rule_ids, tag="faster")   # may return None
    gentler = pick_decay_rule_by_tag(allowed_decay_rule_ids, tag="gentler") # may return None

    if frs_proto_market_risk >= 0.7 and faster:
        return faster
    if frs_proto_market_risk <= 0.3 and frs_participation_index <= 0.4 and gentler:
        return gentler

    return current_decay_rule_id


def propose_itc_policy_adjustments(
    node_id: str,
    current_snapshot: ITCPolicySnapshot,
    signals: Dict[str, Any],
) -> PolicyProposal:
    """
    OAD/COS/FRS/CDS -> suggested tweaks to ITC weighting, scarcity coefficients,
    and decay-rule selection (all within CDS-approved bounds).
    """
    cos = signals["cos"]
    frs = signals["frs"]
    cds = signals["cds"]

    changes: Dict[str, Any] = {}

    # 1) Skill scarcity / overload -> nudge weight bands slightly (bounded later by CDS).
    new_weight_bands = dict(current_snapshot.weight_bands)

    for tier, demand_hours in cos.labor_demand_by_skill.items():
        supply_hours = cos.labor_supply_by_skill.get(tier, 0.0)
        if supply_hours <= 0:
            continue

        ratio = demand_hours / max(supply_hours, 1e-6)  # demand / supply
        band = new_weight_bands.get(tier, WeightingBand(skill_tier=tier, base_multiplier=1.0))

        if ratio > 1.2:
            band.base_multiplier *= 1.05  # +5%
        elif ratio < 0.8:
            band.base_multiplier *= 0.97  # -3%

        new_weight_bands[tier] = band

    changes["weight_bands"] = new_weight_bands

    # 2) Material scarcity / eco stress -> nudge scarcity coefficients.
    new_scarcity_coeffs = dict(current_snapshot.scarcity_coeffs)

    for mat, stress in frs.scarcity_by_material.items():
        coeff = new_scarcity_coeffs.get(mat, 1.0)
        if stress > 0.9:
            coeff *= 1.10
        elif stress > 0.7:
            coeff *= 1.05
        elif stress < 0.3:
            coeff *= 0.97
        new_scarcity_coeffs[mat] = coeff

    changes["scarcity_coeffs"] = new_scarcity_coeffs

    # 3) Decay behavior -> choose among CDS-approved DecayRule IDs.
    allowed_decay_rule_ids = cds.decay_rule_ids  # authoritative list
    new_decay_rule_id = choose_decay_rule_id(
        current_decay_rule_id=current_snapshot.active_decay_rule_id,
        allowed_decay_rule_ids=allowed_decay_rule_ids,
        frs_proto_market_risk=frs.proto_market_risk_score,
        frs_participation_index=frs.participation_index,
    )
    changes["active_decay_rule_id"] = new_decay_rule_id

    rationale = (
        "Auto-generated ITC adjustment proposal based on: "
        "COS demand/supply ratios (skill pressure), "
        "FRS material scarcity and ecological stress, "
        "and CDS-approved decay-rule options under proto-market/participation signals."
    )

    return PolicyProposal(
        id=generate_id(),
        created_at=datetime.utcnow(),
        node_id=node_id,
        changes=changes,
        rationale=rationale,
        generated_by="automatic",
    )
```

***

**CDS Review and Activation**

```python
def cds_review_policy_proposal(
    proposal: PolicyProposal,
    current_snapshot: ITCPolicySnapshot,
    cds_policy_snapshot: Any,
) -> ITCPolicySnapshot:
    """
    CDS review step (sketch):
    - clamp weight bands within CDS min/max multipliers
    - clamp scarcity coeffs within CDS-approved bounds
    - verify decay_rule_id is in cds_policy_snapshot.decay_rule_ids
    - return a new ITCPolicySnapshot if approved, else return current
    """
    bounded_changes = apply_cds_bounds(cds_policy_snapshot, proposal.changes)

    return ITCPolicySnapshot(
        id=generate_id(),
        node_id=current_snapshot.node_id,
        effective_from=datetime.utcnow(),
        cds_policy_snapshot_id=cds_policy_snapshot.id,
        active_decay_rule_id=bounded_changes["active_decay_rule_id"],
        weight_bands=bounded_changes["weight_bands"],
        scarcity_coeffs=bounded_changes["scarcity_coeffs"],
        equivalence_bands=current_snapshot.equivalence_bands,
        notes=proposal.rationale,
        created_from_proposal_id=proposal.id,
    )


def activate_and_broadcast_itc_policy(
    old_snapshot: ITCPolicySnapshot,
    new_snapshot: ITCPolicySnapshot,
    proposal: PolicyProposal,
) -> None:
    """
    Activate the new snapshot and inform Modules 1–8.
    Also write a policy_updated ledger entry for auditability.
    """
    register_itc_policy_snapshot(new_snapshot)

    append_ledger_entry(
        LedgerEntry(
            id=generate_id(),
            timestamp=new_snapshot.effective_from,
            entry_type="policy_updated",
            node_id=new_snapshot.node_id,
            member_id=None,
            related_ids={"proposal_id": proposal.id, "cds_policy_snapshot_id": new_snapshot.cds_policy_snapshot_id},
            details={
                "old_itc_policy_snapshot_id": old_snapshot.id,
                "new_itc_policy_snapshot_id": new_snapshot.id,
                "change_summary": summarize_policy_changes(old_snapshot, new_snapshot),
                "rationale": proposal.rationale,
            },
        )
    )

    notify_labor_capture_service(new_snapshot)
    notify_weighting_engine(new_snapshot)
    notify_decay_scheduler(new_snapshot)
    notify_access_allocation_service(new_snapshot)
    notify_cross_node_reciprocity(new_snapshot)
    notify_ethics_monitor(new_snapshot)
```

***

**Periodic Coordination Tick**

```python
def coordination_tick_for_node(node_id: str) -> Optional[ITCPolicySnapshot]:
    """
    ITC Module 9 periodic loop (daily/weekly):
    1) collect signals
    2) propose bounded adjustments
    3) route to CDS review
    4) activate snapshot + log + broadcast
    """
    current_snapshot = get_current_itc_policy_snapshot(node_id)
    signals = collect_latest_signals(node_id)

    proposal = propose_itc_policy_adjustments(
        node_id=node_id,
        current_snapshot=current_snapshot,
        signals=signals,
    )

    if not has_meaningful_changes(current_snapshot, proposal.changes):
        return None

    cds_policy_snapshot = signals["cds"]  # authoritative bounds
    new_snapshot = cds_review_policy_proposal(
        proposal=proposal,
        current_snapshot=current_snapshot,
        cds_policy_snapshot=cds_policy_snapshot,
    )

    if new_snapshot.id != current_snapshot.id:
        activate_and_broadcast_itc_policy(
            old_snapshot=current_snapshot,
            new_snapshot=new_snapshot,
            proposal=proposal,
        )
        return new_snapshot

    return None
```

***

**Math Sketch — Policy as a Bounded Function of Signals**

Let:
- $\pi(t)$ = ITC policy parameter vector at time $t$ (weight bands, scarcity coefficients, selected decay rule, etc.)
- $S(t)$ = signal vector at time $t$ (COS demand/supply ratios, FRS stress/anomaly indicators, OAD updates)
- $B$ = CDS-imposed bounds and admissible sets (min/max multipliers, allowed decay rule IDs, fairness caps)

A proposed update is:

$$\tilde{\pi}(t) = \pi(t) + \Delta\pi(S(t))$$

Then CDS applies a bounded projection:

$$\pi(t^+) = \mathrm{proj}_B\big(\tilde{\pi}(t)\big)$$

Where $\mathrm{proj}_B$ clamps continuous parameters (e.g., multipliers) and enforces discrete admissibility (e.g., the selected `DecayRule` must be in the CDS-approved set).

---

**Plain-language summary**

Module 9 keeps ITC **responsive** to real conditions (scarcity, bottlenecks, ecological stress, fairness anomalies) while remaining **legitimate** and **non-coercive**: it proposes small parameter shifts, routes them through CDS, and then activates a new auditable policy snapshot for Modules 1–8 to follow—without turning ITC into a market, a currency, or an autonomous governor.
