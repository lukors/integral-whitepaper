#### Module 3 (ITC) — Time-Decay Mechanism

**Purpose**
Prevent ITCs from turning into stored power or proto-wealth by gently decaying balances over time, keeping access aligned with **ongoing participation** instead of past accumulation.

**Role in the system**
Module 2 converts verified labor into **weighted contribution signals** (and later, credited balance updates). Module 3 ensures that credited balances do **not** become permanent entitlements. Rather than hoardable assets, ITCs behave more like metabolic energy: useful and visible, but gradually fading if not renewed through continued operational participation or exercised through access.

Decay parameters are:

- **set and bounded by CDS** (democratically decided, not black-boxed),
- **monitored by FRS** for unintended distributional effects (e.g., penalizing caregivers, disability contexts, temporary crisis),
- **transparent and predictable** to participants.

**Inputs**

- `ITCAccount` (`balance`, `last_decay_applied_at`, `node_id`)
- Active `DecayRule` for the node (CDS-approved)
- Current timestamp
- Optional CDS/FRS modifiers *(e.g., temporary relief flags, crisis windows)*

**Outputs**

- Updated `ITCAccount` with decayed balance and updated `last_decay_applied_at`
- A `LedgerEntry` of type `"itc_decayed"` recording the decay event

***

**Core Logic **

**Registries (illustrative):**

```python
from typing import Dict, Optional
from datetime import datetime

DECAY_RULES: Dict[str, DecayRule] = {}          # node_id -> active DecayRule
ACCOUNTS: Dict[str, ITCAccount] = {}            # account_id -> ITCAccount
LEDGER: Dict[str, LedgerEntry] = {}             # ledger_entry_id -> LedgerEntry


def get_decay_rule(node_id: str) -> DecayRule:
    return DECAY_RULES[node_id]
```

**Compute the decay factor (bounded):**

```python
def compute_decay_factor(elapsed_days: float, rule: DecayRule) -> float:
    """
    Multiplicative decay factor f ∈ (0, 1], applied to balance.

    - No decay within inactivity grace window.
    - Exponential decay beyond grace, with half-life.
    - Bounded by max_annual_decay_fraction to prevent harsh drops.
    """

    # 1) Grace window: no decay
    if elapsed_days <= rule.inactivity_grace_days:
        return 1.0

    effective_days = elapsed_days - rule.inactivity_grace_days

    # 2) Exponential decay with half-life (days)
    H = max(rule.half_life_days, 1e-6)
    raw_factor = 2 ** (-effective_days / H)

    # 3) Annual maximum loss bound (linear-in-time lower bound on factor)
    # If max_annual_decay_fraction = 0.30, then after 1 year factor >= 0.70.
    max_loss = max(0.0, min(1.0, rule.max_annual_decay_fraction))
    year_days = 365.0
    scale = min(elapsed_days / year_days, 1.0)
    min_factor = 1.0 - scale * max_loss

    return max(min_factor, raw_factor)
```

**Apply decay to one account (with floor + ledger entry):**

```python
def apply_decay_to_account(
    account: ITCAccount,
    now: datetime,
    policy_snapshot_id: Optional[str] = None,
) -> ITCAccount:
    """
    ITC Module 3 — Time-Decay Mechanism
    -----------------------------------
    Applies bounded decay to an account’s balance and logs an 'itc_decayed' ledger entry.

    Note: policy_snapshot_id is optional in this sketch; in practice,
    it should reference the CDS policy snapshot in force when decay is applied.
    """

    rule = get_decay_rule(account.node_id)

    elapsed_days = (now - account.last_decay_applied_at).total_seconds() / (3600.0 * 24.0)
    if elapsed_days <= 0:
        return account

    # Small protected floor (optional): do not decay below this
    protected_floor = max(0.0, rule.min_balance_protected)

    # If already at/below protected floor, just advance timestamp
    if account.balance <= protected_floor:
        account.last_decay_applied_at = now
        return account

    factor = compute_decay_factor(elapsed_days=elapsed_days, rule=rule)
    new_balance = max(protected_floor, account.balance * factor)

    decayed_amount = max(0.0, account.balance - new_balance)
    if decayed_amount <= 0:
        account.last_decay_applied_at = now
        return account

    old_balance = account.balance
    account.balance = new_balance
    account.total_decayed += decayed_amount
    account.last_decay_applied_at = now

    # Ledger entry (append-only)
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=now,
        entry_type="itc_decayed",
        node_id=account.node_id,
        member_id=account.member_id,
        related_ids={
            "account_id": account.id,
            "decay_rule_id": rule.id,
            **({"policy_snapshot_id": policy_snapshot_id} if policy_snapshot_id else {}),
        },
        details={
            "old_balance": old_balance,
            "new_balance": new_balance,
            "decayed_amount": decayed_amount,
            "elapsed_days": elapsed_days,
            "decay_factor": factor,
            "protected_floor": protected_floor,
        },
    )
    LEDGER[entry.id] = entry

    return account
```

**Batch decay cycle (daily/weekly job):**

```python
def run_decay_cycle(now: datetime, policy_snapshot_id: Optional[str] = None) -> None:
    for account in ACCOUNTS.values():
        apply_decay_to_account(account, now, policy_snapshot_id=policy_snapshot_id)
```

***

**Math Sketch — Gentle Demurrage, Democratically Bounded**

For an account with balance $B_0$ at last decay time $t_0$, and current time $t$:
- $\Delta t = t - t_0$ in days
- $G$ = inactivity grace period (days)
- $H$ = half-life in days (CDS-approved)
- $\lambda$ = maximum annual decay fraction (e.g., 0.30)
- $B_{\min}$ = protected floor (optional)

**1. No decay within grace**

If $\Delta t \le G$, then $f(\Delta t) = 1$.

**2. Exponential decay beyond grace**

Let $\Delta t' = \Delta t - G$.

$$f_{\text{exp}}(\Delta t') = 2^{-\Delta t'/H}$$

**3. Annual loss bound (minimum factor)**

$$f_{\text{floor}}(\Delta t) = 1 - \lambda \cdot \min\!\left(1, \frac{\Delta t}{365}\right)$$

where the resulting balance is bounded below by a protected floor:

$$B(t) = \max\!\left(B_{\min},\, B_0 \cdot f(\Delta t)\right)$$

**4. Final factor and balance**

$$f(\Delta t) = \max\!\left(f_{\text{floor}}(\Delta t),\, f_{\text{exp}}(\Delta t')\right)$$

**In plain language:** decay begins only after a grace window, proceeds slowly, is bounded against harsh drops, and exists to prevent long-term stockpiling—not to punish pauses in participation. FRS watches distributional outcomes, and CDS can adjust $G$, $H$, $\lambda$, or $B_{\min}$ if distortion appears.
