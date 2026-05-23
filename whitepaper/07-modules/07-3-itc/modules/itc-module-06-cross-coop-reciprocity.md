#### Module 6 (ITC) — Cross-Cooperative & Internodal Reciprocity

**Purpose**

Maintain **coherent meaning of ITCs across nodes** with different ecological conditions, infrastructure capacity, and labor pressures. When people **move between nodes** or **perform work for another node**, their contribution must neither be unfairly devalued nor turned into an arbitrage opportunity.

This module computes **bounded equivalence factors** between nodes so that:

- labor performed under **harder ecological or infrastructural conditions** is not treated as “less,”
- but no one can game the system by choosing nodes for differential ITC yield.

Equivalence here is **interpretive, not exchange-based**. ITCs remain non-transferable and non-tradeable at all times.

**Role in the System**

Module 6 sits at the **federation boundary layer** of ITC:

- Uses **FRS** data on ecological stress, material scarcity, and social strain
- Uses **COS** data on labor pressure, backlog, and local capacity
- Uses **CDS** policy to set **tight bounds** on equivalence variation

It applies equivalence **only** when:

- a member **migrates** to another node, or
- a member **performs labor in a host node** while their ITC account remains rooted in a home node

> **Important distinction:**
>
> - `NodeEquivalenceProfile` represents **diagnostic state** of a node
> - `NodeEquivalenceRule` represents the **bounded interpretation rule** actually applied by ITC

Equivalence is **slow-changing, bounded, public, non-exchangeable**, and applied **only at moments of use or migration**, ensuring it cannot become a currency layer.

***

**Types**

```python
from dataclasses import dataclass
from typing import Dict
from datetime import datetime
```

**Diagnostic Node Profile (Raw Conditions)**

```python
@dataclass
class NodeEquivalenceProfile:
    """
    Diagnostic snapshot of a node's structural conditions
    relevant to ITC interpretation.
    """
    node_id: str
    timestamp: datetime

    eco_constraint_index: float          # 0–1+ (higher = tighter ecological limits)
    material_scarcity_index: float       # 0–1+ (higher = scarcer materials)
    labor_pressure_index: float          # 0–1+ (higher = more backlog / strain)
    infrastructure_strength_index: float # 0–1 (higher = more resilient)

    composite_index: float               # computed scalar (see below)
```

**Applied Equivalence Rule (Bounded Interpretation)**

```python
@dataclass
class NodeEquivalenceRule:
    """
    Bounded interpretation factor mapping ITC meaning
    from one node context to another.
    """
    from_node_id: str
    to_node_id: str
    factor: float                        # bounded (e.g. 0.8–1.2)
    computed_at: datetime
    rationale: Dict[str, float]
```

**Assumed helpers:**

```python
def get_node_equivalence_profile(node_id: str) -> NodeEquivalenceProfile: ...
def get_itc_equivalence_policy() -> Dict: ...
```

**From earlier sections:**

```python
@dataclass
class ITCAccount:
    id: str
    member_id: str
    node_id: str
    balance: float
    last_decay_update: datetime
```

***

**Core Logic**

**1. Composite Index per Node**

Each node’s conditions are compressed into a single scalar:

```python
def compute_node_composite_index(
    profile: NodeEquivalenceProfile,
    policy: Dict,
) -> float:
    """
    Higher index = more constrained / harder operating context.
    """

    w_eco = policy.get("w_eco", 0.4)
    w_scarcity = policy.get("w_scarcity", 0.3)
    w_labor = policy.get("w_labor", 0.3)
    w_infra = policy.get("w_infra", -0.2)  # stronger infrastructure reduces burden

    idx = (
        w_eco * profile.eco_constraint_index +
        w_scarcity * profile.material_scarcity_index +
        w_labor * profile.labor_pressure_index +
        w_infra * profile.infrastructure_strength_index
    )

    return max(idx, policy.get("min_composite_index", 0.1))
```

***

**2. Compute Equivalence Rule Between Nodes**

```python
def compute_node_equivalence_rule(
    from_node: NodeEquivalenceProfile,
    to_node: NodeEquivalenceProfile,
    policy: Dict,
) -> NodeEquivalenceRule:
    """
    Compute bounded interpretation factor between nodes.
    """

    idx_from = compute_node_composite_index(from_node, policy)
    idx_to = compute_node_composite_index(to_node, policy)

    raw_factor = idx_to / idx_from

    max_delta = policy.get("max_equivalence_delta", 0.2)  # ±20%
    min_factor = 1.0 - max_delta
    max_factor = 1.0 + max_delta

    factor = max(min_factor, min(max_factor, raw_factor))

    return NodeEquivalenceRule(
        from_node_id=from_node.node_id,
        to_node_id=to_node.node_id,
        factor=factor,
        computed_at=datetime.utcnow(),
        rationale={
            "idx_from": idx_from,
            "idx_to": idx_to,
            "raw_factor": raw_factor,
            "min_factor": min_factor,
            "max_factor": max_factor,
        },
    )
```

***

**3. Migrating an Account Between Nodes**

```python
def migrate_itc_account_to_node(
    account: ITCAccount,
    new_node_id: str,
    policy: Dict,
) -> None:
    """
    Adjust account balance when a member permanently relocates.
    """

    old_node_id = account.node_id
    if old_node_id == new_node_id:
        return

    from_profile = get_node_equivalence_profile(old_node_id)
    to_profile = get_node_equivalence_profile(new_node_id)
    rule = compute_node_equivalence_rule(from_profile, to_profile, policy)

    account.balance *= rule.factor
    account.node_id = new_node_id

    # Ledger logging recommended (omitted here for brevity)
```

***

**4. Cross-Node Labor (Remote or Federated Work)**

```python
def record_cross_node_labor(
    account: ITCAccount,
    host_node_id: str,
    weighted_hours_local: float,
    policy: Dict,
) -> float:
    """
    Apply host-node meaning to labor, then map into home-node account.
    """

    home_node_id = account.node_id

    host_profile = get_node_equivalence_profile(host_node_id)
    home_profile = get_node_equivalence_profile(home_node_id)

    rule = compute_node_equivalence_rule(
        from_node=host_profile,
        to_node=home_profile,
        policy=policy,
    )

    credits_home = weighted_hours_local * rule.factor
    account.balance += credits_home

    return credits_home
```

***

**Math Sketch — Node Equivalence & Cross-Node Credits**

Let each node $n$ have:
- $E_n$ = ecological constraint
- $S_n$ = material scarcity
- $L_n$ = labor pressure
- $I_n$ = infrastructure strength

Composite index:

$$K_n = \max\left(w_E E_n + w_S S_n + w_L L_n + w_I I_n,\; K_{\min}\right)$$

Raw equivalence:

$$\phi_{a \to b}^{\text{raw}} = \frac{K_b}{K_a}$$

Bounded equivalence:

$$\phi_{a \to b} = \min\!\left(1+\Delta_{\max},\; \max\!\left(1-\Delta_{\max},\; \phi_{a \to b}^{\text{raw}}\right)\right)$$

Account migration:

$$C_b = C_a \cdot \phi_{a \to b}$$

Cross-node labor:

$$C_h = W_m \cdot \phi_{m \to h}$$

Where:
- $W_m$ = weighted contribution in host node
- $C_h$ = credited contribution in home node

Because equivalence is **bounded, public, and non-exchangeable**, this mechanism preserves fairness **without enabling arbitrage**.

***

**In Plain Language**

> Module 6 ensures that "one ITC" retains coherent meaning across diverse conditions—without ever becoming a currency, an exchange rate, or a speculative layer.
