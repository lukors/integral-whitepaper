#### Module 7 (ITC) — Fairness, Anti-Coercion & Ethical Safeguards

**Purpose**

Detect and prevent **proto-market behavior**, coercion, side-deals, and any attempt to transform ITCs into a lever of **power, status, or control**.

This module ensures that:

- no one can **buy or sell labor** using ITCs,
- no one can **hoard influence** via balance accumulation,
- no one can weaponize **scarcity, specialization, or access control**.

It is the **norm-protection layer** that keeps ITC a **coordination signal**, not a currency, wage, or bargaining instrument.

***

**Role in the System**

Module 7 sits above **Modules 1–6** and alongside **FRS**, continuously monitoring system behavior rather than individual intent.

It scans for patterns such as:

- labor-for-ITC side arrangements (“I’ll do this if you give me credits”),
- access queues favoring high-balance members,
- reciprocal sign-offs or collusion between small groups,
- artificial task cycling to evade decay,
- monopolization of high-weight, high-leverage roles.

**Important:**
This module **does not punish, modify balances, or enforce sanctions**.

It **detects, flags, and escalates** patterns to:

- **FRS** (system health & anomaly tracking),
- **CDS** (policy review, ethical deliberation, training interventions).

Enforcement, if any, is **always human-governed** and policy-bound.

***

**Core Type — Ethics Flag**

```python
from dataclasses import dataclass
from typing import List, Literal
from datetime import datetime


@dataclass
class ITCEthicsFlag:
    """
    Diagnostic flag for potential ethical violations in ITC dynamics.
    Detection only — enforcement is handled by CDS processes.
    """
    id: str
    flag_type: Literal[
        "proto_market_exchange",
        "coercion_pattern",
        "queue_bias",
        "decay_evasion",
        "role_monopoly",
        "other_anomaly",
    ]
    account_ids: List[str]
    related_task_ids: List[str]
    related_transaction_ids: List[str]
    description: str
    severity: Literal["low", "medium", "high"]
    created_at: datetime
    status: Literal["open", "under_review", "resolved"]
    notes: str = ""
```

Assumed registries (conceptual):

```python
ETHICS_FLAGS: Dict[str, ITCEthicsFlag] = {}
```

***

**Core Detection Heuristics**

**1. Proto-Market Exchange Detection**

Goal: detect patterns resembling **payment for labor** using ITCs.

Typical signal:

- Account **A** redeems or transfers ITCs shortly after **B** completes labor,
- A did not participate in that labor,
- The pattern is **bilateral, repeated, and time-coupled**.

```python
def detect_proto_market_exchange(
    labor_events: List[LaborEvent],
    transactions: List[ITCTransaction],
    policy: Dict,
) -> List[ITCEthicsFlag]:
    """
    Detect repeated, bilateral timing correlations between one account's
    labor events and another account's ITC transfers/redeptions.
    """

    events_by_account: Dict[str, List[LaborEvent]] = {}
    for ev in labor_events:
        events_by_account.setdefault(ev.account_id, []).append(ev)

    flags: List[ITCEthicsFlag] = []

    candidate_pairs = policy.get("candidate_account_pairs", [])
    time_window_hours = policy.get("proto_market_time_window_hours", 6.0)
    min_repeats = policy.get("proto_market_min_repeats", 3)

    for a_id, b_id in candidate_pairs:
        pattern_count = 0
        related_tasks = set()
        related_tx = set()

        for ev in events_by_account.get(b_id, []):
            for tx in transactions:
                if tx.from_account_id == a_id and tx.timestamp >= ev.end_time:
                    dt = (tx.timestamp - ev.end_time).total_seconds() / 3600
                    if 0 <= dt <= time_window_hours:
                        pattern_count += 1
                        related_tasks.add(ev.task_id)
                        related_tx.add(tx.id)

        if pattern_count >= min_repeats:
            flags.append(
                ITCEthicsFlag(
                    id=generate_id(),
                    flag_type="proto_market_exchange",
                    account_ids=[a_id, b_id],
                    related_task_ids=list(related_tasks),
                    related_transaction_ids=list(related_tx),
                    description=(
                        f"Repeated timing correlation suggests possible "
                        f"labor-for-ITC side arrangement between {a_id} and {b_id}."
                    ),
                    severity="medium",
                    created_at=datetime.utcnow(),
                    status="open",
                )
            )

    return flags
```

***

**2. Queue Bias / Balance Privilege Detection**

Goal: ensure **access priority** is not implicitly tied to ITC balance.

```python
def detect_queue_bias(
    access_logs: List[AccessDecisionLog],
    accounts: Dict[str, ITCAccount],
    policy: Dict,
) -> List[ITCEthicsFlag]:
    """
    Detect systematic correlation between ITC balance and priority access.
    """

    flags: List[ITCEthicsFlag] = []
    min_decisions = policy.get("queue_bias_min_decisions", 30)
    min_corr = policy.get("queue_bias_min_correlation", 0.5)

    by_resource: Dict[str, List[AccessDecisionLog]] = {}
    for log in access_logs:
        by_resource.setdefault(log.resource_id, []).append(log)

    for resource_id, logs in by_resource.items():
        if len(logs) < min_decisions:
            continue

        balances, ranks = [], []
        for log in logs:
            acc = accounts.get(log.account_id)
            if acc:
                balances.append(acc.balance)
                ranks.append(log.priority_rank)

        if len(balances) < min_decisions:
            continue

        corr = compute_negative_correlation(balances, ranks)

        if corr >= min_corr:
            flags.append(
                ITCEthicsFlag(
                    id=generate_id(),
                    flag_type="queue_bias",
                    account_ids=list({log.account_id for log in logs}),
                    related_task_ids=[],
                    related_transaction_ids=[],
                    description=(
                        f"Strong correlation detected between ITC balance "
                        f"and access priority for resource {resource_id}."
                    ),
                    severity="medium",
                    created_at=datetime.utcnow(),
                    status="open",
                )
            )

    return flags
```

***

**3. Role Monopoly & Decay-Evasion Detection**

Goal: prevent control concentration or artificial work loops.

```python
def detect_role_monopoly(
    labor_events: List[LaborEvent],
    policy: Dict,
) -> List[ITCEthicsFlag]:
    """
    Detect over-concentration of critical tasks among a small set of accounts.
    """

    flags: List[ITCEthicsFlag] = []
    critical_tasks = policy.get("critical_task_ids", [])
    min_events = policy.get("role_monopoly_min_events", 50)
    max_share = policy.get("role_monopoly_max_share", 0.6)

    for task_id in critical_tasks:
        events = [e for e in labor_events if e.task_id == task_id]
        if len(events) < min_events:
            continue

        count_by_account: Dict[str, int] = {}
        for e in events:
            count_by_account[e.account_id] = count_by_account.get(e.account_id, 0) + 1

        total = len(events)
        top_account, top_count = max(count_by_account.items(), key=lambda x: x[1])

        if top_count / total >= max_share:
            flags.append(
                ITCEthicsFlag(
                    id=generate_id(),
                    flag_type="role_monopoly",
                    account_ids=[top_account],
                    related_task_ids=[task_id],
                    related_transaction_ids=[],
                    description=(
                        f"Account {top_account} performs a disproportionate share "
                        f"({top_count/total:.0%}) of critical task {task_id}."
                    ),
                    severity="low",
                    created_at=datetime.utcnow(),
                    status="open",
                )
            )

    return flags
```

Decay-evasion detection follows the same structure: closed-loop task cycling without COS necessity.

***

**Orchestrating Ethics Monitoring**

```python
def run_itc_ethics_monitoring_cycle(
    labor_events: List[LaborEvent],
    transactions: List[ITCTransaction],
    access_logs: List[AccessDecisionLog],
    accounts: Dict[str, ITCAccount],
    policy: Dict,
) -> List[ITCEthicsFlag]:
    """
    Periodic ITC ethics monitoring.
    """

    flags: List[ITCEthicsFlag] = []

    flags.extend(detect_proto_market_exchange(labor_events, transactions, policy))
    flags.extend(detect_queue_bias(access_logs, accounts, policy))
    flags.extend(detect_role_monopoly(labor_events, policy))
    # detect_decay_evasion(...), detect_coercion_patterns(...)

    for f in flags:
        ETHICS_FLAGS[f.id] = f

    return flags
```

***

**Math Sketch — Ethical Pattern Indicators**

**1. Queue Bias Correlation**

Let:
- $B_i$ = ITC balance
- $R_i$ = priority rank (lower is better)

Compute:

$$\rho = \text{corr}(B_i,\ -R_i)$$

If:

$$\rho \ge \rho_{\min}$$

over sufficient samples → flag **queue bias**.

---

**2. Proto-Market Exchange Score**

For account pair $(a, b)$:

$$M_{a,b} = \frac{N_{a\to b} + N_{b\to a}}{N_{\text{baseline}} + \varepsilon}$$

If:

$$M_{a,b} \ge M_{\text{threshold}}$$

→ flag **proto-market exchange**.

---

**In Plain Language**

> Module 7 ensures ITCs never become money by making misuse **visible, diagnosable, and correctable**.

No hidden markets. No coercive leverage. No silent power accumulation. Just transparent signals feeding democratic governance.
