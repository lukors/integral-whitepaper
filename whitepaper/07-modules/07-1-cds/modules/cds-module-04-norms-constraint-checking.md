#### Module 4 (CDS) — Norms & Constraint Checking Module

**Purpose**

Module 4 serves as the **viability filter** for proposals and scenarios. Its role is not to *choose* among options, but to enforce the **ecological, material, technical, safety, fairness, and constitutional boundaries** within which all decisions must remain.

It ensures that:

- proposals do not exceed ecological thresholds
- resource demands reflect actual COS capacities
- labor demands match real availability
- social/fairness constraints (via ITC) are respected
- the proposal does not violate node-level or federated constitutional principles
- safety and longevity criteria are satisfied

A proposal that fails a constraint is **not rejected outright**—it is returned with **specific modification requirements**, enabling structured revision rather than political conflict.

**Inputs**

- `ContextModel` from Module 3
- `StructuredIssueView` from Module 2
- Formal constraints from:
  - **FRS** ecological threshold tables
  - **COS** labor and resource availability
  - **ITC** fairness and accessibility rules
  - **CDS constitutional layer** (node charter, federated rules, policy snapshots)

**Outputs**

- `ConstraintReport`: pass/fail results, violations, required modifications
- Updated issue lifecycle state:
  - `issue.status = "constrained"`
  - `issue.last_updated_at` set
- A filtered set of feasible scenarios for Module 5 and 6 *(or a set of “revise-and-retry” requirements if all fail)*

------

**Helper Type for Reporting**

*(Use the canonical type consistent with the updated CDS data model.)*

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime

@dataclass
class ConstraintReport:
    issue_id: str
    scenario_id: str
    passed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    required_modifications: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

------

**Core Logic **

```python
from datetime import datetime
from typing import Dict, Any

def check_constraints(
    issue: Issue,
    scenario: Scenario,
    context: ContextModel,
    rules: Dict[str, Any],
) -> ConstraintReport:
    """
    Module 4 — Norms & Constraint Checking
    --------------------------------------
    Validates a scenario against ecological, material, labor, fairness,
    and constitutional boundaries. Returns a structured report rather
    than a simple pass/fail.
    """
    now = datetime.utcnow()

    violations = []
    modifications = []

    # 1) Ecological thresholds (FRS-informed, CDS-bounded)
    for key, limit in rules.get("ecological", {}).items():
        if scenario.indicators.get(key, 0) > limit:
            violations.append({"type": "ecology", "detail": f"{key} exceeds {limit}"})
            modifications.append(f"Reduce {key} below {limit}")

    # 2) Resource availability (COS)
    for resource, amount_needed in scenario.parameters.get("materials", {}).items():
        available = context.resources.get(resource, 0)
        if amount_needed > available:
            violations.append({"type": "resources", "detail": f"{resource} insufficient"})
            modifications.append(f"Find alternative or reduce {resource} usage")

    # 3) Labor capacity & scheduling (COS)
    required_labor = scenario.parameters.get("labor_hours_required", 0)
    available_labor = context.labor.get("available_hours", 0)
    if required_labor > available_labor:
        violations.append({"type": "labor", "detail": "labor capacity exceeded"})
        modifications.append("Rescope, phase, or reschedule labor distribution")

    # 4) Social & fairness constraints (ITC + CDS norms)
    max_access_risk = rules.get("social", {}).get("max_access_risk", None)
    if max_access_risk is not None:
        if scenario.parameters.get("accessibility_risk", 0) > max_access_risk:
            violations.append({"type": "fairness", "detail": "accessibility risk too high"})
            modifications.append("Revise design for universal access compliance")

    # 5) Constitutional / procedural constraints (CDS)
    for key, requirement in rules.get("constitutional", {}).items():
        if not requirement(scenario):
            violations.append({"type": "constitutional", "detail": f"{key} violated"})
            modifications.append(f"Modify scenario to satisfy {key}")

    passed = len(violations) == 0

    # Update issue lifecycle state
    issue.status = "constrained"
    issue.last_updated_at = now

    return ConstraintReport(
        issue_id=issue.id,
        scenario_id=scenario.id,
        passed=passed,
        violations=violations,
        required_modifications=modifications,
        created_at=now,
        metadata={"timestamp": now.isoformat()},
    )
```

------

**Math Sketch — Constraint Check as Multi-Domain Feasibility**

A scenario $S$ is viable only if it satisfies:

$$S \in \mathcal{F}_{eco},\quad S \in \mathcal{F}_{res},\quad S \in \mathcal{F}_{lab},\quad S \in \mathcal{F}_{soc},\quad S \in \mathcal{F}_{const}$$

Where each feasibility set defines a constraint domain:

**Ecological**

$$\forall i,\; E_i(S) \leq E_i^{max}$$

**Resource**

$$R_j(S) \leq R_j^{available}$$

**Labor**

$$L(S) \leq L^{available}$$

**Fairness & Social**

$$A(S) \leq A^{threshold}$$

**Constitutional**

$$C_k(S) = \text{True} \;\; \forall k$$

If any domain fails, the scenario is returned for revision with specificity, not rejected in total.

---

**Semantic Summary**

Module 4 determines whether a proposal is:
- **ecologically viable**
- **materially feasible**
- **labor-coherent**
- **fair and accessible**
- **constitutionally permissible**

If not, it produces a structured modification set. If yes, the scenario proceeds to deliberation and consensus. This module functions as the **ecological–constitutional immune system** of CDS.
