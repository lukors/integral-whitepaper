#### Module 6 (CDS) — Weighted Consensus Mechanism

**Purpose**

Module 6 transforms refined scenarios and structured objections from Module 5 into a **formal consensus result**.

Unlike voting systems, it does **not** count heads or choose winners. Instead, it synthesizes:

- preference gradients (strength of support)
- principled objections (severity × scope)
- required conditions for approval
- epistemic uncertainty
- fairness considerations
- scenario interdependencies

The purpose is to produce a **non-coercive, mathematically transparent measure of agreement** that supports:

- approval
- conditional approval
- revision & resubmission
- escalation to **Module 9** (high-bandwidth human deliberation)

It is a consensus mechanism, **not a voting system**.

**Inputs**

- `DeliberationState` from Module 5
- List of `Vote` objects submitted by participants
- Consolidated `Objection` set
- Participant weights (from CDS constitutional rules; usually 1.0)
- Optional equalizer weights (if constitutionally defined)

**Outputs**

- `ConsensusResult` containing:
  - consensus score
  - objection index
  - required conditions for approval (if any)
  - directive: `approve | revise | escalate_to_module9`
- Updated issue lifecycle state:
  - `issue.status = "consensus_check"`
  - `issue.last_updated_at` set

***

**Helper Type: ConsensusResult (canonical)**

```python

from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime

@dataclass
class ConsensusResult:
    issue_id: str
    scenario_id: str
    consensus_score: float
    objection_index: float
    directive: str  # "approve" | "revise" | "escalate_to_module9"
    required_conditions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

***

**Core Logic **

```python

from datetime import datetime
from typing import List, Dict


def compute_consensus(
    issue: Issue,
    scenario: Scenario,
    votes: List[Vote],
    objections: List[Objection],
    participant_weights: Dict[str, float],   # participant_id -> weight
    consensus_threshold: float,
    block_threshold: float,
) -> ConsensusResult:
    """
    Module 6 — Weighted Consensus Mechanism
    ---------------------------------------
    Computes:
      - preference-gradient consensus score (weighted)
      - objection index from principled objections
      - directive: approve / revise / escalate_to_module9
    """
    now = datetime.utcnow()

    # Update issue lifecycle state
    issue.status = "consensus_check"
    issue.last_updated_at = now

    # 1) Map qualitative support levels to numeric scores
    scale = {
        "strong_support": 1.0,
        "support": 0.6,
        "neutral": 0.0,
        "concern": -0.4,
        "block": -1.0,
    }

    # 2) Weighted preference aggregation: sum(w_i * p_i) / sum(w_i)
    weighted_sum = 0.0
    weight_total = 0.0

    for v in votes:
        w = float(participant_weights.get(v.participant_id, 1.0))
        p = float(scale[v.support])
        weighted_sum += w * p
        weight_total += w

    consensus_score = (weighted_sum / weight_total) if weight_total > 0 else 0.0

    # 3) Objection index: max(severity * scope)
    objection_index = max([obj.severity * obj.scope for obj in objections] or [0.0])

    # 4) Blocking objection check (non-coercive safeguard)
    if objection_index >= block_threshold:
        return ConsensusResult(
            issue_id=issue.id,
            scenario_id=scenario.id,
            consensus_score=consensus_score,
            objection_index=objection_index,
            directive="revise",
            required_conditions=["Resolve high-severity objection(s)."],
            metadata={"reason": "objection_block", "timestamp": now.isoformat()},
        )

    # 5) If consensus is below threshold → revise
    if consensus_score < consensus_threshold:
        return ConsensusResult(
            issue_id=issue.id,
            scenario_id=scenario.id,
            consensus_score=consensus_score,
            objection_index=objection_index,
            directive="revise",
            required_conditions=["Increase support or address concerns."],
            metadata={"reason": "insufficient_consensus", "timestamp": now.isoformat()},
        )

    # 6) If consensus is sufficient but value conflict persists → escalate to Module 9
    if (
        consensus_score >= consensus_threshold
        and objection_index > 0.0
        and objection_index < block_threshold
        and unresolved_value_conflict(objections)
    ):
        return ConsensusResult(
            issue_id=issue.id,
            scenario_id=scenario.id,
            consensus_score=consensus_score,
            objection_index=objection_index,
            directive="escalate_to_module9",
            required_conditions=[],
            metadata={"reason": "values_conflict_requires_module9", "timestamp": now.isoformat()},
        )

    # 7) Otherwise: approve
    return ConsensusResult(
        issue_id=issue.id,
        scenario_id=scenario.id,
        consensus_score=consensus_score,
        objection_index=objection_index,
        directive="approve",
        required_conditions=[],
        metadata={"reason": "approved", "timestamp": now.isoformat()},
    )
```

***

**Math Sketch: Consensus Score & Objection Index**

**1. Preference Gradient (Weighted)**

For votes $v_i$ with participant weights $w_i$ and mapped preference values $p_i$:

$$C = \frac{\sum_i w_i p_i}{\sum_i w_i}$$

This produces a **continuous consensus metric**, not a binary vote.

**2. Objection Index**

Each objection has:
- severity $s_i \in [0,1]$
- scope $w_i \in [0,1]$

The objection index is:

$$O = \max_i (s_i \cdot w_i)$$

This ensures serious objections cannot be overridden by numeric dominance.

**3. Approval Conditions**

A scenario is approved if:

$$C \ge C_{\text{threshold}} \quad \text{and} \quad O < O_{\text{block}}$$

If:
- $C < C_{\text{threshold}}$ → revise
- $O \ge O_{\text{block}}$ → revise (blocking objection)
- contradictory signals / value conflict → escalate to Module 9

---

**Semantic Summary**

The Weighted Consensus Mechanism:
- handles qualitative preferences numerically
- protects principled minority concerns
- maintains transparency and non-coercion
- returns a clear directive:
  - **approve**
  - **revise**
  - **escalate to Module 9**

It is the **decision-synthesis mechanism** of CDS—while the formal **Decision** object itself is recorded in Module 7 and dispatched in Module 8.
