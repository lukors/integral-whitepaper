#### Module 6 (COS) — Distribution & Access Flow Coordination

**Purpose**

Route finished goods into **Access Centers, shared-use pools, repair loops, and delivery channels**, while generating **availability/scarcity signals** that ITC uses (within CDS bounds) to compute and adjust access obligations. This is where “we built X” becomes “here’s how X is actually available to people.”

**Role in the system**

Up to now:

- **OAD** → designed and certified the artifact.
- **COS 1–5** → planned, staffed, sourced, and built it in real space.
- **ITC** → can compute a *prospective* access obligation from design + production assumptions.

**Module 6** closes the loop between production and lived access:

- decides **where** finished units go (personal acquisition stock, shared fleets, essential-service reserves, repair pools),
- tracks **stock vs requests** (availability, backlog),
- detects **scarcity** and **misallocation** patterns (e.g., personal stock drained while shared stock sits idle),
- emits **non-market signals** to:
  - **ITC** (availability/backlog multipliers as *inputs*, not prices),
  - **FRS** (access stress signals for long-horizon monitoring).

This is the federation’s **distribution nervous system**: not price formation, not bidding—just transparent routing plus measured availability.

------

**Types — Access Channels, Inventory, and Signals**

```py
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime

class AccessChannelType(str, Enum):
    PERSONAL = "personal_acquisition"        # long-term possession, ITCs extinguished (ITC side)
    SHARED_FLEET = "shared_fleet"            # pooled use (bikes, instruments, devices)
    TOOL_LIBRARY = "tool_library"            # short-term borrow, typically free
    ESSENTIAL_SERVICE = "essential_service"  # reserved availability for essential provisioning
    REPAIR_POOL = "repair_pool"              # held for swap/repair/reconditioning loop

@dataclass
class DistributionPolicy:
    """
    Default routing policy for a good in a node.
    COS normalizes splits and enforces minimum/priority constraints.
    """
    default_split: Dict[AccessChannelType, float]   # weights (need not sum to 1)
    prioritize_essential: bool = False              # reserve a minimum essential stock
    min_essential_units: int = 0                    # optional: hard minimum for ESSENTIAL_SERVICE
    min_shared_fraction: float = 0.0                # ensure some share remains in SHARED_FLEET/TOOL_LIBRARY

@dataclass
class AccessInventoryRecord:
    """
    Current state of a good across channels in a node.
    """
    good_id: str
    node_id: str
    by_channel: Dict[AccessChannelType, int]

    pending_requests_personal: int = 0
    pending_requests_shared: int = 0
    pending_requests_essential: int = 0

    # optional timestamp for windowed monitoring
    updated_at: Optional[datetime] = None

@dataclass
class ITCAccessAvailabilitySignal:
    """
    Advisory signal to ITC Module 5: availability/backlog conditions that can
    gently modulate access obligations (within CDS-defined bounds).
    """
    good_id: str
    node_id: str
    availability_index_personal: float
    availability_index_shared: float
    backlog_ratio_personal: float
    backlog_ratio_shared: float
    suggested_access_multiplier: float   # >1 scarcity; <1 abundance (advisory)
    notes: str = ""

@dataclass
class FRSAccessStressSignal:
    """
    Monitoring signal to FRS: persistent scarcity, over-demand, or underutilization patterns.
    """
    good_id: str
    node_id: str
    scarcity_index: float               # 0–1 (higher = scarcer)
    underutilization_index: float       # 0–1 (higher = more idle relative to demand proxy)
    description: str
```

------

**Core Logic**

1) Routing finished goods into channels

```python
def _normalize_split(split: Dict[AccessChannelType, float]) -> Dict[AccessChannelType, float]:
    total = sum(split.values())
    if total <= 0:
        # sensible fallback: default to shared circulation
        return {AccessChannelType.SHARED_FLEET: 1.0}
    return {ch: w / total for ch, w in split.items()}

def route_finished_goods(
    finished_units: int,
    policy: DistributionPolicy,
    inv: AccessInventoryRecord,
) -> AccessInventoryRecord:
    """
    Route newly finished units into access channels using:
    - normalized default split
    - optional essential reservation
    - optional minimum shared fraction
    """
    if finished_units <= 0:
        inv.updated_at = datetime.utcnow()
        return inv

    split = _normalize_split(policy.default_split)
    allocated: Dict[AccessChannelType, int] = {ch: 0 for ch in AccessChannelType}

    remaining = finished_units

    # --- A) Optional essential reservation (first claim) ---
    if policy.prioritize_essential and policy.min_essential_units > 0:
        current_essential = inv.by_channel.get(AccessChannelType.ESSENTIAL_SERVICE, 0)
        needed = max(0, policy.min_essential_units - current_essential)
        reserve = min(needed, remaining)
        allocated[AccessChannelType.ESSENTIAL_SERVICE] += reserve
        remaining -= reserve

    # --- B) Deterministic base allocation using floor, then distribute remainder by largest fractional part ---
    # Compute exact desired counts
    desired = {ch: split.get(ch, 0.0) * remaining for ch in AccessChannelType}
    base = {ch: int(desired[ch]) for ch in AccessChannelType}  # floor
    used = sum(base.values())

    # Ensure we don't exceed remaining (shouldn’t, due to floor)
    used = min(used, remaining)
    for ch in AccessChannelType:
        base[ch] = min(base[ch], remaining)  # defensive

    leftover = remaining - sum(base.values())

    # Distribute leftover by fractional remainders (largest first)
    remainders = sorted(
        [(ch, desired[ch] - base[ch]) for ch in AccessChannelType],
        key=lambda x: x[1],
        reverse=True,
    )
    for i in range(leftover):
        allocated[remainders[i % len(remainders)][0]] += 1

    # Add base floors
    for ch in AccessChannelType:
        allocated[ch] += base[ch]

    # --- C) Enforce minimum shared fraction (shared_fleet + tool_library) ---
    total_after = sum(inv.by_channel.values()) + finished_units
    min_shared_units = int(policy.min_shared_fraction * total_after)

    current_shared = (
        inv.by_channel.get(AccessChannelType.SHARED_FLEET, 0)
        + inv.by_channel.get(AccessChannelType.TOOL_LIBRARY, 0)
    )
    new_shared = allocated[AccessChannelType.SHARED_FLEET] + allocated[AccessChannelType.TOOL_LIBRARY]

    deficit = max(0, min_shared_units - (current_shared + new_shared))
    if deficit > 0:
        # pull from PERSONAL first (least communal), then from REPAIR_POOL if needed
        pull_order = [AccessChannelType.PERSONAL, AccessChannelType.REPAIR_POOL]
        for src in pull_order:
            if deficit <= 0:
                break
            take = min(deficit, allocated[src])
            allocated[src] -= take
            allocated[AccessChannelType.SHARED_FLEET] += take
            deficit -= take

    # --- D) Commit allocation to inventory ---
    for ch in AccessChannelType:
        inv.by_channel[ch] = inv.by_channel.get(ch, 0) + allocated[ch]

    inv.updated_at = datetime.utcnow()
    return inv
```

------

2) Availability + backlog indices (simple, computable)

We interpret:

- personal stock $S_p$ vs personal requests $R_p$
- shared stock $S_s$ vs shared requests $R_s$

```python
def compute_availability_metrics(inv: AccessInventoryRecord, epsilon: float = 1e-6) -> Dict[str, float]:
    S_p = inv.by_channel.get(AccessChannelType.PERSONAL, 0)
    S_s = inv.by_channel.get(AccessChannelType.SHARED_FLEET, 0) + inv.by_channel.get(AccessChannelType.TOOL_LIBRARY, 0)

    R_p = inv.pending_requests_personal
    R_s = inv.pending_requests_shared

    # Availability indices
    A_p = 1.0 if (R_p <= 0 and S_p > 0) else (min(1.0, S_p / max(R_p, epsilon)) if R_p > 0 else 0.0)
    A_s = 1.0 if (R_s <= 0 and S_s > 0) else (min(1.0, S_s / max(R_s, epsilon)) if R_s > 0 else 0.0)

    # Backlog ratios
    B_p = max(R_p - S_p, 0) / max(R_p, 1)
    B_s = max(R_s - S_s, 0) / max(R_s, 1)

    return {"A_p": A_p, "A_s": A_s, "B_p": B_p, "B_s": B_s}
```

------

3) Availability → advisory multiplier signal for ITC

```python
def build_itc_access_availability_signal(
    good_id: str,
    node_id: str,
    inv: AccessInventoryRecord,
    gamma_scarcity: float = 0.4,
    gamma_backlog: float = 0.4,
    m_min: float = 0.7,
    m_max: float = 1.5,
) -> ITCAccessAvailabilitySignal:
    metrics = compute_availability_metrics(inv)
    A_p, A_s = metrics["A_p"], metrics["A_s"]
    B_p, B_s = metrics["B_p"], metrics["B_s"]

    scarcity = 0.5 * (1.0 - A_p) + 0.5 * (1.0 - A_s)
    backlog = 0.5 * B_p + 0.5 * B_s

    m = 1.0 + gamma_scarcity * scarcity + gamma_backlog * backlog
    m = max(m_min, min(m_max, m))

    return ITCAccessAvailabilitySignal(
        good_id=good_id,
        node_id=node_id,
        availability_index_personal=A_p,
        availability_index_shared=A_s,
        backlog_ratio_personal=B_p,
        backlog_ratio_shared=B_s,
        suggested_access_multiplier=m,
        notes="Advisory signal from COS Module 6 (availability/backlog). ITC applies CDS bounds.",
    )
```

------

4) Stress signal for FRS (scarcity + underutilization proxy)

```python
def build_frs_access_stress_signal(
    good_id: str,
    node_id: str,
    inv: AccessInventoryRecord,
) -> FRSAccessStressSignal:
    metrics = compute_availability_metrics(inv)
    A_p, A_s = metrics["A_p"], metrics["A_s"]
    B_p, B_s = metrics["B_p"], metrics["B_s"]

    # scarcity in [0,1]
    scarcity = 0.5 * (1.0 - A_p) + 0.5 * (1.0 - A_s)

    total_stock = sum(inv.by_channel.values())
    total_requests = inv.pending_requests_personal + inv.pending_requests_shared + inv.pending_requests_essential

    # underutilization proxy: “lots of stock with weak expressed demand”
    if total_stock <= 0:
        underutilization = 0.0
    else:
        demand_pressure = min(1.0, total_requests / max(total_stock, 1))
        underutilization = 1.0 - demand_pressure  # high when stock >> requests

    desc = (
        f"Access stress for {good_id} in {node_id}: "
        f"scarcity={scarcity:.2f}, underutilization={underutilization:.2f}, "
        f"backlog_personal={B_p:.2f}, backlog_shared={B_s:.2f}."
    )

    return FRSAccessStressSignal(
        good_id=good_id,
        node_id=node_id,
        scarcity_index=scarcity,
        underutilization_index=underutilization,
        description=desc,
    )
```

------

5) Orchestration: end-to-end pass for Module 6

```python
def run_distribution_and_access_flow(
    good_id: str,
    node_id: str,
    finished_units: int,
    policy: DistributionPolicy,
    inventory: AccessInventoryRecord,
) -> Dict[str, object]:
    """
    COS Module 6 — Distribution & Access Flow Coordination
    ------------------------------------------------------
    1) Route newly produced goods into access channels.
    2) Compute availability/backlog metrics.
    3) Produce advisory ITC signal + FRS stress signal.
    """
    updated_inventory = route_finished_goods(
        finished_units=finished_units,
        policy=policy,
        inv=inventory,
    )

    itc_signal = build_itc_access_availability_signal(
        good_id=good_id,
        node_id=node_id,
        inv=updated_inventory,
    )

    frs_signal = build_frs_access_stress_signal(
        good_id=good_id,
        node_id=node_id,
        inv=updated_inventory,
    )

    return {
        "inventory": updated_inventory,
        "itc_access_signal": itc_signal,
        "frs_access_stress": frs_signal,
    }
```

------

**Math Sketch — Availability and Backlog**

Let:
- $S_p$ = personal stock
- $R_p$ = personal requests
- $S_s$ = shared stock (shared fleet + tool library)
- $R_s$ = shared requests

Personal availability:

$$
A_p = \min\left(1,\; \frac{S_p}{\max(R_p,\epsilon)}\right)
$$

Shared availability:

$$
A_s = \min\left(1,\; \frac{S_s}{\max(R_s,\epsilon)}\right)
$$

Personal backlog ratio:

$$
B_p = \frac{\max(R_p - S_p, 0)}{\max(R_p, 1)}
$$

Shared backlog ratio:

$$
B_s = \frac{\max(R_s - S_s, 0)}{\max(R_s, 1)}
$$

Scarcity index (0–1) used for signaling:

$$
\text{scarcity} = \tfrac{1}{2}(1-A_p) + \tfrac{1}{2}(1-A_s)
$$

Bounded advisory multiplier to ITC:

$$
m = \mathrm{clip}\left(1 + \gamma_1\cdot \text{scarcity} + \gamma_2\cdot \tfrac{1}{2}(B_p + B_s),\; m_{\min},\; m_{\max}\right)
$$

---

**Plain-Language Example**

A node completes **20 bicycles**.

Policy says:
- 40% personal stock
- 40% shared fleet
- 20% repair pool
- minimum shared fraction enforced

COS routes bikes accordingly, updates inventory counts, and sees that:
- personal requests are high and personal stock is tight → backlog rising
- shared fleet stock is adequate → shared availability remains good

COS sends ITC an **advisory signal**:
- "Personal access is currently tight, shared access is fine; here is a bounded multiplier suggestion."

ITC can then, within CDS bounds:
- nudge the personal acquisition obligation upward slightly (to avoid draining stock),
- keep shared access near-free (or lightly gated only under scarcity),
- and expose the rationale transparently.

FRS receives the longer-horizon signal:
- "Chronic personal-bike scarcity + healthy shared stock → consider shifting future routing/production strategy or strengthening shared-use culture."
