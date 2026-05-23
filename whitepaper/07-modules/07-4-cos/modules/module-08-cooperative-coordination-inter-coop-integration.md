#### Module 8 (COS) — Cooperative Coordination & Inter-Coop Integration

**Purpose**

Coordinate multiple cooperative units (workspaces, labs, material centers, logistics groups, etc.) within and across nodes so production is **distributed, non-hierarchical, and resilient**—and so **dependency structure** (internal vs federated vs transitional external; robust vs fragile) becomes **computable input** for ITC valuation and FRS risk monitoring.

**Role in the system**

Upstream:

- **OAD** specifies required processes and inputs (“to make this good, you need these capabilities”).
- **COS 1–5** planned and executed local production.
- **COS 6–7** handled distribution and QA.

Module 8 zooms out to the **network layer**:

- Which cooperative units (internal, federated, transitional external) are involved?
- How much capacity does each contribute?
- Where are the **single points of failure** (concentration)?
- Where are the **structural gaps** (missing capabilities)?
- How should work be routed when multiple units/nodes can perform the same capability?

Outputs:

- A **coordination profile** (who does what, where).
- A **dependency/fragility picture** ITC can use as an *advisory* valuation input (external reliance and fragility → higher systemic burden).
- A **systemic autonomy/fragility signal** for FRS to track resilience and long-range risk.

Importantly: COS does **not** assume every material/process has a dedicated coop. “Cooperative units” are generic: any organized workspace/service contributing to production.

**Inputs**

- Required capabilities and their demand (from OAD + COS plan)
- Known cooperative units and capabilities (internal, federated, transitional external)
- Current routing / assignment (what share is being handled by which unit)
- QA history / reliability signals (from COS Module 7), as optional quality inputs

**Outputs**

- `GoodsCoordinationProfile` (dependencies + derived indices)
- `ITCDependencySignal` (advisory multiplier input to ITC Module 5, bounded by CDS policy)
- `FRSAutonomySignal` (risk/fragility monitoring input)

***

**Types — Cooperative Units, Dependencies, and Signals**

```python
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum
from datetime import datetime


class CoopScope(str, Enum):
    INTERNAL = "internal"                      # inside the node
    FEDERATED = "federated"                    # another Integral node
    EXTERNAL_TRANSITIONAL = "external_transitional"  # outside Integral; temporary


@dataclass
class CoopCapability:
    """
    A capability a cooperative unit can provide.
    Examples: 'frame_welding', 'wood_processing', 'luthiery_finish', 'logistics'.
    """
    capability_id: str
    description: str
    max_throughput_per_period: float   # e.g. units/week
    current_utilization: float         # 0–1
    quality_score: float               # 0–1 (empirical QA history)


@dataclass
class CooperativeUnit:
    """
    Any organized workspace/service contributing to production.
    """
    unit_id: str
    node_id: str
    scope: CoopScope
    capabilities: Dict[str, CoopCapability]     # capability_id -> capability
    ecological_impact_index: float              # 0–1+ aggregate operational EII
    notes: str = ""


@dataclass
class CoopDependency:
    """
    One link in the capability web for a given good/version.
    """
    unit_id: str
    node_id: str
    scope: CoopScope
    capability_id: str
    share_of_process: float                     # fraction of this capability demand routed here (0–1)
    critical: bool                              # if this fails, does production halt?


@dataclass
class GoodsCoordinationProfile:
    good_id: str
    version_id: str
    node_id: str
    dependencies: List[CoopDependency] = field(default_factory=list)

    # Derived shares across scopes
    internal_share: float = 0.0
    federated_share: float = 0.0
    external_share: float = 0.0

    # Derived resilience indicators
    autonomy_index: float = 0.0                 # 0–1 (higher = less externally dependent)
    fragility_index: float = 0.0                # 0–1 (higher = more concentrated / vulnerable)

    notes: str = ""


@dataclass
class ITCDependencySignal:
    """
    Advisory valuation input for ITC Module 5.
    Note: ITC must still apply CDS bounds/fairness rules.
    """
    good_id: str
    version_id: str
    node_id: str
    autonomy_index: float
    fragility_index: float
    external_share: float
    suggested_access_multiplier: float
    notes: str = ""


@dataclass
class FRSAutonomySignal:
    """
    System monitoring input: external dependence + fragility picture.
    """
    good_id: str
    version_id: str
    node_id: str
    autonomy_index: float
    fragility_index: float
    external_share: float
    critical_external_links: int
    description: str
```

***

**Core Logic**

1) Build a Coordination Profile

This aggregates routing assignments into a single profile and normalizes scope shares.

```python
def build_goods_coordination_profile(
    good_id: str,
    version_id: str,
    node_id: str,
    routing: Dict[str, List[CoopDependency]],
) -> GoodsCoordinationProfile:
    """
    routing: capability_id -> list of CoopDependency describing how that capability
             is split across units.
    """
    dependencies: List[CoopDependency] = []
    s_int = 0.0
    s_fed = 0.0
    s_ext = 0.0

    for cap_id, deps in routing.items():
        for dep in deps:
            dependencies.append(dep)
            if dep.scope == CoopScope.INTERNAL:
                s_int += dep.share_of_process
            elif dep.scope == CoopScope.FEDERATED:
                s_fed += dep.share_of_process
            else:
                s_ext += dep.share_of_process

    total = s_int + s_fed + s_ext
    if total > 0:
        internal_share = s_int / total
        federated_share = s_fed / total
        external_share = s_ext / total
    else:
        internal_share = federated_share = external_share = 0.0

    return GoodsCoordinationProfile(
        good_id=good_id,
        version_id=version_id,
        node_id=node_id,
        dependencies=dependencies,
        internal_share=internal_share,
        federated_share=federated_share,
        external_share=external_share,
    )
```

2) Compute Autonomy and Fragility

- **Autonomy** rewards internal + federated execution, penalizes transitional external dependence.
- **Fragility** rises when the work is concentrated in few units and/or when critical external links exist.

```python
from collections import defaultdict

def compute_autonomy_and_fragility(
    profile: GoodsCoordinationProfile,
    alpha: float = 1.0,      # internal weight
    beta: float = 0.7,       # federated weight (still inside Integral)
    gamma: float = 1.0,      # external penalty
    external_critical_penalty: float = 0.3,
    min_autonomy: float = 0.0,
    max_autonomy: float = 1.0,
) -> GoodsCoordinationProfile:

    s_int = profile.internal_share
    s_fed = profile.federated_share
    s_ext = profile.external_share

    # Autonomy (clipped 0–1)
    A_raw = alpha * s_int + beta * s_fed - gamma * s_ext
    A = max(min_autonomy, min(max_autonomy, A_raw))

    # Concentration (Herfindahl-like): sum of squared unit shares
    share_by_unit = defaultdict(float)
    external_critical_share = 0.0

    for dep in profile.dependencies:
        share_by_unit[dep.unit_id] += dep.share_of_process
        if dep.scope == CoopScope.EXTERNAL_TRANSITIONAL and dep.critical:
            external_critical_share += dep.share_of_process

    total = sum(share_by_unit.values())
    if total > 0:
        for u in list(share_by_unit.keys()):
            share_by_unit[u] /= total

    H = sum(s**2 for s in share_by_unit.values())  # 0..1-ish

    # Fragility (clipped 0–1)
    F_raw = H + external_critical_penalty * external_critical_share
    F = max(0.0, min(1.0, F_raw))

    profile.autonomy_index = A
    profile.fragility_index = F
    profile.notes = (
        f"Autonomy={A:.3f}, Fragility={F:.3f}; "
        f"shares: internal={s_int:.3f}, federated={s_fed:.3f}, external={s_ext:.3f}."
    )
    return profile
```

3) Emit Advisory ITC Signal

This proposes a bounded multiplier that ITC Module 5 *may* incorporate—**but ITC still must apply CDS fairness rules and bounds**.

```python
def build_itc_dependency_signal(
    profile: GoodsCoordinationProfile,
    F_ref: float = 0.30,
    A_ref: float = 0.50,
    k1: float = 0.40,
    k2: float = 0.40,
    m_min: float = 0.70,
    m_max: float = 1.50,
) -> ITCDependencySignal:

    A = profile.autonomy_index
    F = profile.fragility_index
    s_ext = profile.external_share

    m_raw = 1.0 + k1 * (F - F_ref) - k2 * (A - A_ref)
    m = max(m_min, min(m_max, m_raw))

    return ITCDependencySignal(
        good_id=profile.good_id,
        version_id=profile.version_id,
        node_id=profile.node_id,
        autonomy_index=A,
        fragility_index=F,
        external_share=s_ext,
        suggested_access_multiplier=m,
        notes=(
            f"Advisory multiplier from coordination structure: "
            f"A={A:.3f}, F={F:.3f}, ext_share={s_ext:.3f} → m={m:.3f}."
        ),
    )
```

4) Emit FRS Autonomy Signal

```python
def build_frs_autonomy_signal(profile: GoodsCoordinationProfile) -> FRSAutonomySignal:
    critical_external_links = sum(
        1 for d in profile.dependencies
        if d.scope == CoopScope.EXTERNAL_TRANSITIONAL and d.critical
    )

    desc = (
        f"{profile.good_id} (v={profile.version_id}, node={profile.node_id}): "
        f"autonomy={profile.autonomy_index:.3f}, fragility={profile.fragility_index:.3f}, "
        f"external_share={profile.external_share:.3f}, critical_external_links={critical_external_links}."
    )

    return FRSAutonomySignal(
        good_id=profile.good_id,
        version_id=profile.version_id,
        node_id=profile.node_id,
        autonomy_index=profile.autonomy_index,
        fragility_index=profile.fragility_index,
        external_share=profile.external_share,
        critical_external_links=critical_external_links,
        description=desc,
    )
```

5) Orchestration

```python
def run_coop_coordination_pipeline(
    good_id: str,
    version_id: str,
    node_id: str,
    routing: Dict[str, List[CoopDependency]],
) -> Dict[str, object]:

    profile = build_goods_coordination_profile(
        good_id=good_id,
        version_id=version_id,
        node_id=node_id,
        routing=routing,
    )

    profile = compute_autonomy_and_fragility(profile)

    itc_signal = build_itc_dependency_signal(profile)
    frs_signal = build_frs_autonomy_signal(profile)

    return {
        "coordination_profile": profile,
        "itc_dependency_signal": itc_signal,
        "frs_autonomy_signal": frs_signal,
    }
```

Triggered when:

- a new product line starts in a node,
- routing patterns/capacities change,
- or FRS/ITC request reevaluation after a shock.

***

**Math Sketch — Network-Level Autonomy and Fragility**

Let the following quantities be defined:
- $s_{\text{int}}$: total share routed to **internal** cooperative units
- $s_{\text{fed}}$: total share routed to **federated** (inter-node) cooperative units
- $s_{\text{ext}}$: total share routed to **external transitional** units

These represent how the production process for a given good is distributed across scopes.

Let:
- $s_i$ be the **normalized share** of the total process handled by cooperative unit $i$

Let:
- $E$ be the **total share of the process routed through critical external links**
  (i.e., links whose failure would halt production)

**Autonomy Index**

First compute the raw autonomy score:

$$
A_{\text{raw}} = \alpha\, s_{\text{int}} + \beta\, s_{\text{fed}} - \gamma\, s_{\text{ext}}
$$

Then clip the value to the unit interval:

$$
A = \mathrm{clip}(A_{\text{raw}},\, 0,\, 1)
$$

**Fragility Index**

Compute a concentration measure (Herfindahl-style):

$$
H = \sum_i s_i^2
$$

Add a penalty for critical external dependence:

$$
F_{\text{raw}} = H + \lambda E
$$

Then clip to the unit interval:

$$
F = \mathrm{clip}(F_{\text{raw}},\, 0,\, 1)
$$

**Advisory Valuation Multiplier (ITC Input)**

Define a **bounded advisory multiplier** used by ITC as one input to access-value computation:

$$
m = \mathrm{clip}\!\left(
1 + k_1 (F - F_0) - k_2 (A - A_0),
\; m_{\min},\; m_{\max}
\right)
$$

**Interpretation in Plain Language**

Module 8 answers: **"What does this good depend on, and how fragile is that dependency web?"**

- If production depends heavily on **transitional external** suppliers or on a **single critical unit**, fragility rises.
- If production is distributed across internal + federated capacity, autonomy rises.
- ITC can use this as a **bounded advisory input** (not a price signal) to reflect systemic risk and encourage long-run autonomy.
- FRS uses it to track resilience trends and prompt long-horizon planning: "what should we internalize, federate, or redesign to reduce fragility?"
