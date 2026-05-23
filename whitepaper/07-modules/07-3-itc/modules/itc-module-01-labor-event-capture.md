#### Module 1 (ITC) — Labor Event Capture & Verification

**Purpose**
Record and authenticate **operational** labor so every ITC-relevant event reflects *real, voluntary, socially necessary work*—not just “time someone said they spent.”

**Role in the system**
This module is the **sensory interface** of the ITC system. It listens to COS task flows and cooperative logs, and only accepts labor that:

- is linked to a **real operational task** in COS (production, maintenance, logistics, etc.)
- is performed by an **authenticated member**
- is **verified** by peers or supervisors (and optionally instruments/sensors)
- fits within reasonable duration bounds

Output is a clean stream of `LaborEvent` objects. They are **value-neutral** until Module 2 applies weighting.

***

**Inputs**

- Authenticated member identity (`member_id`)
- COS task/workflow reference (`task_id`, `coop_id`, `node_id`)
- Start/end timestamps, task label, and context
- One or more verifiers (peer/supervisor IDs)
- Optional metadata (station ID, batch ID, tool ID, etc.)

**Outputs**

- A validated `LaborEvent`
- A corresponding `LedgerEntry` of type `"labor_event_recorded"`
   *(weighting happens later; this is the audit record of capture + verification)*

***

**Core Logic **

```python
from typing import Dict, List, Optional, Any
from datetime import datetime

# Pretend registries (illustrative only)
ITC_ACCOUNTS: Dict[str, ITCAccount] = {}         # key could be member_id or account_id depending on implementation
LABOR_EVENTS: Dict[str, LaborEvent] = {}         # event_id -> LaborEvent
LEDGER: Dict[str, LedgerEntry] = {}              # entry_id -> LedgerEntry (append-only list is also fine)

# Helpers (stubs)
def generate_id() -> str:
    ...

def authenticate_member(member_id: str) -> bool:
    """
    Verify identity (DID + signature etc.). Stubbed here.
    """
    return member_id in ITC_ACCOUNTS

def cos_task_exists(coop_id: str, task_id: str, node_id: str) -> bool:
    """
    Check with COS that this task is real, currently active, and operational.
    """
    return True

def is_operational_task(task_id: str) -> bool:
    """
    Ensure this is material/operational work, not governance or pure ideation.
    """
    return not task_id.startswith(("GOV-", "IDEA-"))

def verify_peers(verifiers: List[str], member_id: str) -> bool:
    """
    Verification policy:
    - at least one verifier
    - verifiers cannot all be the same as the worker
    """
    if not verifiers:
        return False
    return any(v != member_id for v in verifiers)

def compute_hours(start: datetime, end: datetime) -> float:
    delta = end - start
    return max(0.0, delta.total_seconds() / 3600.0)


def capture_labor_event(
    member_id: str,
    coop_id: str,
    node_id: str,
    task_id: str,
    task_label: str,
    start_time: datetime,
    end_time: datetime,
    skill_tier: SkillTier,
    context: Dict[str, Any],
    verifiers: List[str],
    metadata: Dict[str, Any],
    max_hours_per_event: float = 12.0,
) -> LaborEvent:
    """
    ITC Module 1 — Labor Event Capture & Verification
    -------------------------------------------------
    Capture one operational labor event, validate it against COS and
    cooperative norms, and store a verified LaborEvent for downstream weighting.
    """

    # -------------------------
    # 1) Authentication & task legitimacy
    # -------------------------
    assert authenticate_member(member_id), "unauthenticated member"
    assert cos_task_exists(coop_id, task_id, node_id), "unknown or inactive task"
    assert is_operational_task(task_id), "non-operational tasks do not earn ITCs"

    # -------------------------
    # 2) Time & duration checks
    # -------------------------
    assert end_time > start_time, "end_time must be after start_time"
    hours = compute_hours(start_time, end_time)

    if hours <= 0.0:
        raise ValueError("zero or negative labor duration")
    if hours > max_hours_per_event:
        raise ValueError(f"labor event exceeds maximum allowed duration ({hours:.2f}h)")

    # -------------------------
    # 3) Peer / supervisor verification
    # -------------------------
    if not verify_peers(verifiers, member_id):
        raise ValueError("insufficient or invalid peer verification")

    verified_at = datetime.utcnow()

    # -------------------------
    # 4) Create and store LaborEvent (value-neutral)
    # -------------------------
    event_id = generate_id()
    event = LaborEvent(
        id=event_id,
        member_id=member_id,
        coop_id=coop_id,
        task_id=task_id,
        task_label=task_label,
        node_id=node_id,
        start_time=start_time,
        end_time=end_time,
        hours=hours,
        skill_tier=skill_tier,
        context=context,
        verified_by=verifiers,
        verification_timestamp=verified_at,
        metadata=metadata,
    )
    LABOR_EVENTS[event_id] = event

    # -------------------------
    # 5) Append audit record (Module 8 uses these)
    # -------------------------
    entry = LedgerEntry(
        id=generate_id(),
        timestamp=verified_at,
        entry_type="labor_event_recorded",
        node_id=node_id,
        member_id=member_id,
        related_ids={
            "event_id": event_id,
            "task_id": task_id,
            "coop_id": coop_id,
        },
        details={
            "hours": hours,
            "skill_tier": skill_tier,
            "context": context,
            "verified_by": verifiers,
            "task_label": task_label,
        },
    )
    LEDGER[entry.id] = entry

    return event
```

**Plain-language summary:**
Only labor that is **(1) authenticated, (2) tied to a real COS operational task, (3) time-sane, and (4) peer-verified** enters ITC. Everything else is rejected or flagged upstream. This ensures ITC credit begins from **trusted operational reality**, not self-reporting or social influence.

**Math Sketch — Validity & Social Necessity Filter**

Let each submitted labor claim be a tuple:

$$e = (m, t, h, v)$$

where:
- $m$ = member ID
- $t$ = task ID
- $h$ = claimed hours
- $v$ = set of verifiers

Define indicator functions:
- $A(m) = 1$ if member is authenticated, else $0$
- $O(t) = 1$ if task $t$ is operational and registered in COS, else $0$
- $H(h) = 1$ if $0 < h \leq H_{\max}$, else $0$
- $V(v,m) = 1$ if $\exists\, v_i \in v : v_i \ne m$, else $0$

Define overall validity:

$$\text{valid}(e) = A(m) \cdot O(t) \cdot H(h) \cdot V(v,m)$$

An event is accepted iff:

$$\text{valid}(e) = 1$$

**Note:** $H_{\max}$ represents the configured maximum allowable hours per labor event (e.g., `max_hours_per_event = 12`), ensuring claims remain within reasonable operational bounds.

> A labor event enters the ITC system only if it is **authenticated**, **operationally and socially necessary** (linked to COS), **time-sane**, and **peer verified**. Only then can Module 2 interpret and weight it as contribution.
