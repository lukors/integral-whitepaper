#### Module 5 (CDS) — Participatory Deliberation Workspace

**Purpose**

Module 5 provides a **transparent, structured, multi-user deliberation environment** where participants can:

- interpret structured issues (Module 2),
- review contextual evidence (Module 3),
- examine constraint reports (Module 4),
- refine proposals,
- submit principled objections,
- resolve misunderstandings, and
- co-develop scenario modifications.

This is the “collective reasoning” stage—the module that turns information into shared understanding.

It does **not** decide. It organizes and clarifies human reasoning so the consensus engine (Module 6) can operate on clean, coherent data.

**Inputs**

- `StructuredIssueView` from Module 2
- `ContextModel` from Module 3
- `ConstraintReport` from Module 4
- Submissions and revisions from participants
- Optional mediation signals (e.g., from facilitators or CDS norms engine)

**Outputs**

- A refined set of scenarios or scenario variants
- A consolidated objections list
- A structured dataset ready for weighted consensus in Module 6
- Updated issue lifecycle state:
  - `issue.status = "deliberation"`
  - `issue.last_updated_at` set

------

**Helper Type**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class DeliberationState:
    issue_id: str
    active_scenarios: List[Scenario] = field(default_factory=list)
    objections: List[Objection] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

*(Note: `DeliberationState` is a transient workspace representation—useful for downstream computation and optional trace logging, but not the canonical CDS record itself. Canonical trace is captured in Module 7.)*

------

**Core Logic **

```python
from datetime import datetime
from typing import List, Dict, Any


def deliberate(
    issue: Issue,
    scenarios: List[Scenario],
    context: ContextModel,
    constraint_reports: List[ConstraintReport],
    incoming_objections: List[Objection],
    participant_notes: List[Dict[str, Any]],
) -> DeliberationState:
    """
    Module 5 — Participatory Deliberation Workspace
    ------------------------------------------------
    Creates the structured deliberation environment where:
      - participants refine proposals
      - objections are aggregated and clarified
      - constraint reports are interpreted
      - scenario variants may be proposed

    Note:
      - Module 5 does not decide.
      - It outputs a clean, consensus-ready deliberation state for Module 6.
    """
    now = datetime.utcnow()

    # Build an index for constraint reports by scenario_id (avoid order dependence)
    cr_by_scenario: Dict[str, ConstraintReport] = {cr.scenario_id: cr for cr in constraint_reports}

    # 1) Keep scenarios that either pass constraints OR have explicit modifications (revise-and-retry)
    feasible_scenarios: List[Scenario] = []
    scenario_variants: List[Scenario] = []

    for s in scenarios:
        cr = cr_by_scenario.get(s.id)

        if cr is None:
            # If no constraint report exists, keep scenario but flag as needing constraint evaluation
            feasible_scenarios.append(s)
            continue

        if cr.passed:
            feasible_scenarios.append(s)

        elif cr.required_modifications:
            # Generate a modified scenario variant (revision candidate)
            modified = apply_modifications(s, cr.required_modifications)
            scenario_variants.append(modified)

        # If it failed and has no modifications, it is not carried forward

    active_scenarios = feasible_scenarios + scenario_variants

    # 2) Integrate and normalize objections (dedup + merge)
    resolved_objections = normalize_objections(incoming_objections)

    # 3) Sanitize and record participant notes for traceability
    clean_notes = sanitize_notes(participant_notes)

    # Update issue lifecycle state
    issue.status = "deliberation"
    issue.last_updated_at = now

    return DeliberationState(
        issue_id=issue.id,
        active_scenarios=active_scenarios,
        objections=resolved_objections,
        notes=clean_notes,
        updated_at=now,
        metadata={
            "updated": now.isoformat(),
            "num_active_scenarios": len(active_scenarios),
            "num_objections": len(resolved_objections),
            "num_notes": len(clean_notes),
        },
    )
```

------

**Math Sketch — Objection Aggregation**

In deliberation, objections must be:
- aggregated
- normalized
- merged when duplicates arise
- distinguished by severity and scope

Let each objection $o_i$ have severity $s_i \in [0,1]$ and scope $w_i \in [0,1]$.

Define **objection influence**:

$$I(o_i) = s_i \cdot w_i$$

Cluster objections using cosine similarity on embeddings:

$$\text{sim}(o_a, o_b) = \frac{e(o_a)\cdot e(o_b)}{\|e(o_a)\| \|e(o_b)\|}$$

Objections within similarity threshold $\tau_{obj}$ are merged:

$$O_k = \bigcup_{i:\, \text{sim}(o_i, O_k) > \tau_{obj}} o_i$$

And the merged objection's influence is:

$$I(O_k) = \max_{o_i \in O_k} I(o_i)$$

This ensures even a small minority with high-severity, high-scope objections cannot be silenced or diluted.

---

**Semantic Summary**

Module 5 is where the community actually *thinks.* It provides a structured deliberation environment where:
- ideas are clarified
- misunderstandings resolved
- objections aggregated
- scenarios modified
- constraint reports interpreted
- cooperation emerges organically

The output is a refined, consensus-ready set of options that Module 6 can evaluate using weighted preference gradients—keeping CDS a **human-centered deliberation engine**, not just an automated evaluator.
