#### Module 8 (ITC) — Ledger, Transparency & Auditability

**Purpose**

Maintain a **single, tamper-evident, queryable history** of everything ITC touches:

- labor events and their weighting
- ITC crediting, decay, and redemption
- cross-node equivalence band application
- access decisions and access-values
- ethics flags and policy changes that affect valuation

The goal is **trust by inspection**, not trust by faith: anyone can see *why* something is valued as it is, *how* someone’s balance evolved, and *what* rules were in force at the time.

**Role in the System**

Module 8 is the **nervous system log**. It:

- records **all state-changing ITC operations** as append-only entries,
- computes **integrity hashes** so tampering is detectable,
- provides **public, filtered views** for members and co-ops,
- allows CDS/FRS to reconstruct sequences and run audits,
- exposes enough structure that you can trace:
   “This bike’s access-value = X ITCs because of these OAD/COS/FRS parameters + these policies at time T.”

It is **not** a blockchain or speculative token ledger. It is a **cybernetic audit log**: fast, structured, verifiable, and tied directly to real-world tasks and access.

------

**Core Types**

We reuse your high-level `LedgerEntry` and add a tiny integrity layer.

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Literal
from datetime import datetime
import hashlib
import json


LedgerEntryType = Literal[
    "labor_event_recorded",
    "labor_weight_applied",
    "itc_credited",
    "itc_decayed",
    "access_value_quoted",
    "access_redeemed",
    "equivalence_band_applied",
    "ethics_flag_created",
    "ethics_flag_resolved",
    "policy_updated",
]


@dataclass
class LedgerEntry:
    """
    Canonical, append-only record of an ITC-relevant event.
    """
    id: str
    timestamp: datetime
    entry_type: LedgerEntryType
    node_id: str

    member_id: Optional[str] = None
    related_ids: Dict[str, str] = field(default_factory=dict)  # {"event_id": "...", "item_id": "...", ...}
    details: Dict[str, Any] = field(default_factory=dict)      # JSON-like payload

    # Integrity fields
    prev_hash: Optional[str] = None
    entry_hash: Optional[str] = None


# Global store (conceptual)
LEDGER: List[LedgerEntry] = []
LEDGER_INDEX_BY_ID: Dict[str, LedgerEntry] = {}
```

Integrity helper

```python
def compute_entry_hash(entry: LedgerEntry) -> str:
    """
    Compute a deterministic hash for a ledger entry (excluding entry_hash itself).
    """
    serializable = {
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat(),
        "entry_type": entry.entry_type,
        "node_id": entry.node_id,
        "member_id": entry.member_id,
        "related_ids": entry.related_ids,
        "details": entry.details,
        "prev_hash": entry.prev_hash,
    }
    data = json.dumps(serializable, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
```

Appending to the ledger

```python
def append_ledger_entry(entry: LedgerEntry) -> LedgerEntry:
    """
    Append an entry to the global ledger, linking it to the prior hash.
    """
    prev_hash = LEDGER[-1].entry_hash if LEDGER else None
    entry.prev_hash = prev_hash
    entry.entry_hash = compute_entry_hash(entry)

    LEDGER.append(entry)
    LEDGER_INDEX_BY_ID[entry.id] = entry
    return entry
```

This creates a **hash-chained log**: change any old entry → all downstream hashes break.

------

**Recording Key ITC Events**

Any time a module mutates state (or creates a state-bearing artifact like a valuation), it writes a ledger entry.

**1) Labor event recorded (Module 1)**

```python
def log_labor_event_recorded(event: LaborEvent) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=event.end_time,
        entry_type="labor_event_recorded",
        node_id=event.node_id,
        member_id=event.member_id,
        related_ids={"event_id": event.id, "task_id": event.task_id, "coop_id": event.coop_id},
        details={
            "hours": event.hours,
            "skill_tier": event.skill_tier,
            "context": event.context,
            "verified_by": event.verified_by,
            "verification_timestamp": event.verification_timestamp.isoformat(),
        },
    )
    append_ledger_entry(entry)
```

**2) Labor weight applied (Module 2)**

```python
def log_labor_weight_applied(
    event: LaborEvent,
    weighted_record: WeightedLaborRecord,
) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=weighted_record.created_at,
        entry_type="labor_weight_applied",
        node_id=event.node_id,
        member_id=event.member_id,
        related_ids={"event_id": event.id, "weighted_record_id": weighted_record.id},
        details={
            "base_hours": weighted_record.base_hours,
            "weight_multiplier": weighted_record.weight_multiplier,
            "weighted_hours": weighted_record.weighted_hours,
            "breakdown": weighted_record.breakdown,
        },
    )
    append_ledger_entry(entry)
```

**3) ITC credited / decayed (Modules 2–3)**

```python
def log_itc_credited(
    account: ITCAccount,
    amount: float,
    reason: str,
    related_ids: Optional[Dict[str, str]] = None,
) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=datetime.utcnow(),
        entry_type="itc_credited",
        node_id=account.node_id,
        member_id=account.member_id,
        related_ids=related_ids or {},
        details={
            "amount": amount,
            "new_balance": account.balance,
            "reason": reason,
            "account_id": account.id,
        },
    )
    append_ledger_entry(entry)


def log_itc_decayed(
    account: ITCAccount,
    amount_lost: float,
    decay_rule_id: str,
    elapsed_days: float,
    decay_factor: float,
) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=datetime.utcnow(),
        entry_type="itc_decayed",
        node_id=account.node_id,
        member_id=account.member_id,
        related_ids={"decay_rule_id": decay_rule_id},
        details={
            "amount_lost": amount_lost,
            "remaining_balance": account.balance,
            "elapsed_days": elapsed_days,
            "decay_factor": decay_factor,
            "account_id": account.id,
        },
    )
    append_ledger_entry(entry)
```

**4) Access value quote & redemption (Module 5)**

```python
def log_access_value_quoted(access_val: AccessValuation) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=access_val.computed_at,
        entry_type="access_value_quoted",
        node_id=access_val.node_id,
        member_id=None,  # a quote can be system-wide, not per-member
        related_ids={"item_id": access_val.item_id, "design_version_id": access_val.design_version_id},
        details={
            "final_itc_cost": access_val.final_itc_cost,
            "base_weighted_labor_hours": access_val.base_weighted_labor_hours,
            "eco_burden_adjustment": access_val.eco_burden_adjustment,
            "material_scarcity_adjustment": access_val.material_scarcity_adjustment,
            "repairability_credit": access_val.repairability_credit,
            "longevity_credit": access_val.longevity_credit,
            "policy_snapshot_id": access_val.policy_snapshot_id,
            "rationale": access_val.rationale,
            "valid_until": access_val.valid_until.isoformat() if access_val.valid_until else None,
        },
    )
    append_ledger_entry(entry)


def log_access_redeemed(record: RedemptionRecord, account: ITCAccount) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=record.redemption_time,
        entry_type="access_redeemed",
        node_id=record.node_id,
        member_id=record.member_id,
        related_ids={"item_id": record.item_id, "redemption_id": record.id},
        details={
            "itc_spent": record.itc_spent,
            "new_balance": account.balance,
            "redemption_type": record.redemption_type,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "valuation_snapshot": {
                "final_itc_cost": record.access_valuation_snapshot.final_itc_cost,
                "policy_snapshot_id": record.access_valuation_snapshot.policy_snapshot_id,
            },
        },
    )
    append_ledger_entry(entry)
```

**5) Equivalence band applied (Module 6)**

```python
def log_equivalence_band_applied(
    member_id: str,
    node_id: str,
    band: EquivalenceBand,
    context: Dict[str, Any],
) -> None:
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=datetime.utcnow(),
        entry_type="equivalence_band_applied",
        node_id=node_id,
        member_id=member_id,
        related_ids={"home_node_id": band.home_node_id, "local_node_id": band.local_node_id},
        details={
            "labor_context_factor": band.labor_context_factor,
            "eco_context_factor": band.eco_context_factor,
            "notes": band.notes,
            "context": context,  # e.g. {"event": "travel", "access_center_id": "..."}
        },
    )
    append_ledger_entry(entry)
```

Ethics + policy updates are logged similarly via `"ethics_flag_created"`, `"ethics_flag_resolved"`, `"policy_updated"`.

------

**Query & Audit Helpers**

```python
def get_member_history(member_id: str) -> List[LedgerEntry]:
    return sorted(
        [e for e in LEDGER if e.member_id == member_id],
        key=lambda e: e.timestamp,
    )


def get_item_valuation_history(item_id: str) -> List[LedgerEntry]:
    return sorted(
        [
            e for e in LEDGER
            if e.entry_type == "access_value_quoted"
            and e.related_ids.get("item_id") == item_id
        ],
        key=lambda e: e.timestamp,
    )


def verify_ledger_integrity() -> bool:
    prev_hash = None
    for entry in LEDGER:
        if entry.prev_hash != prev_hash:
            return False
        if compute_entry_hash(entry) != entry.entry_hash:
            return False
        prev_hash = entry.entry_hash
    return True
```

------

**Math Sketch — Hash-Chained Audit Log**

We can think of the ledger as an ordered sequence:

$$L = \{ e_1, e_2, \dots, e_N \}$$

Each entry $e_k$ contains:
- a payload $P_k$ (event metadata),
- the previous hash $H_{k-1}$,
- and its own hash $H_k$.

Define:

$$H_k = h\left( P_k,\ H_{k-1} \right)$$

where $h$ is a cryptographic hash (e.g. SHA-256), and $H_0$ is a fixed constant (or `None` encoded).

**Tamper-evidence property:** if any payload $P_i$ is modified, then $\tilde{H}_i \ne H_i$ and all downstream hashes break.

---

**Transparency & Calculation Traceability**

For a particular good $g$ at time $t$, suppose Module 5 computed an access-value:

$$C_g(t) = f\left( L_g, E_g, S_g, R_g, M_g, \dots,\ \Pi(t) \right)$$

where:
- $L_g$ = labor components
- $E_g$ = ecological coefficients
- $S_g$ = scarcity factors
- $R_g$ = repairability / lifecycle burden
- $M_g$ = material intensity & embodied energy
- $\Pi(t)$ = policy parameters at time $t$

The ledger stores:
- `labor_event_recorded` + `labor_weight_applied` entries supporting $L_g$
- `policy_updated` entries reconstructing $\Pi(t)$
- `access_value_quoted` entries storing the component breakdown used by $f$

Thus anyone can reconstruct:
1. which data fed the valuation function,
2. which policy bounds were active,
3. what access-value was produced and why.

This directly answers:

> "How did you arrive at 37 ITCs for this bicycle?"

…without a market, a price system, or a black-box bureaucracy.
