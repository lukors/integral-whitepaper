#### Module 9 (OAD) — Validation, Certification & Release Manager

**Purpose**

To act as the **final gate** between exploratory design work and real-world deployment, certifying only those design versions that meet Integral’s ecological, safety, lifecycle, labor, and integration standards.

**Role in the system**

Modules 1–8 generate and improve candidate designs. **Module 9 decides which of those become “production-grade” artifacts** that COS can schedule and ITC can value.

This module:

- aggregates evaluation outputs from Modules 3–8
- checks them against **explicit certification criteria**
- creates a `CertificationRecord`
- updates the `DesignVersion` status to `"certified"` (or routes it back for revision)
- prepares metadata needed for **Module 10** (Knowledge Commons & Reuse Repository)
- flags certified designs to **COS** and **ITC** as deployable references

Without Module 9, there is no separation between prototypes and approved infrastructure.

**Certification is not necessarily permanent.**
If later FRS feedback shows divergence between modeled and real-world performance, certification can be **revoked** or the design can be **superseded** by a revised version (with full traceability).

**Inputs**

For a given `DesignVersion`:

- `EcoAssessment` (Module 3)
- `LifecycleModel` (Module 4)
- `LaborProfile` (Module 6)
- `SimulationResult` (Module 5)
- `IntegrationCheck` (Module 7)
- `OptimizationResult` (Module 8), if used
- Node/federation certification policy (thresholds, sector norms, safety minima)

**Outputs**

- `CertificationRecord` for `version_id`
- Updated `DesignVersion.status` (typically `"certified"` or `"under_review"`)
- A structured bundle of metrics for:
  - **COS** (production + maintenance planning)
  - **ITC** (access-value computation)
  - **Module 10** (repository indexing)

***

**Reminder: CertificationRecord**

```python
@dataclass
class CertificationRecord:
    version_id: str
    certified_at: datetime
    certified_by: List[str]
    criteria_passed: List[str]
    criteria_failed: List[str]
    documentation_bundle_uri: str
    status: Literal["certified", "revoked", "pending"]
```

***

**Core Validation & Certification Logic**

Certification is treated as a **policy-composed decision** across five dimensions:

1. Ecology
2. Safety & Feasibility
3. Lifecycle & Maintainability
4. Labor & Ergonomics
5. Systems Integration

Each checker returns:

- `passed: bool`
- `reason: str`
- `risk_score: float` (0–1)

***

1) **Per-dimension checkers** 

```python
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime


def check_ecology(
    eco: EcoAssessment,
    max_eco_score: float = 0.5
) -> Tuple[bool, str, float]:
    passed = eco.eco_score <= max_eco_score
    risk = min(1.0, eco.eco_score / max_eco_score) if max_eco_score > 0 else 1.0
    reason = "ok" if passed else f"eco_score={eco.eco_score:.2f} exceeds {max_eco_score:.2f}"
    return passed, reason, risk


def check_safety_and_feasibility(
    sim: SimulationResult,
    min_feasibility: float = 0.7,
    min_yield_factor: float = 1.2
) -> Tuple[bool, str, float]:
    feas_ok = sim.feasibility_score >= min_feasibility
    yield_factor = sim.safety_margins.get("yield_factor", 0.0)
    safety_ok = yield_factor >= min_yield_factor

    passed = feas_ok and safety_ok and not sim.failure_modes

    reasons = []
    if not feas_ok:
        reasons.append(f"feasibility={sim.feasibility_score:.2f} < {min_feasibility:.2f}")
    if not safety_ok:
        reasons.append(f"yield_factor={yield_factor:.2f} < {min_yield_factor:.2f}")
    if sim.failure_modes:
        reasons.append(f"failure_modes={sim.failure_modes}")

    reason = "ok" if passed else "; ".join(reasons) or "simulation concerns"

    feas_risk = 1.0 - sim.feasibility_score
    safety_risk = max(0.0, (min_yield_factor - yield_factor) / max(min_yield_factor, 1e-6))
    risk = max(0.0, min(1.0, 0.6 * feas_risk + 0.4 * safety_risk))

    return passed, reason, risk


def estimate_expected_lifetime_hours(
    version: DesignVersion,
    lifecycle: LifecycleModel
) -> float:
    """
    Convert lifecycle.expected_lifetime_years into hours using usage assumptions.
    """
    usage = version.parameters.get("usage_assumptions", {"hours_per_day": 4.0, "days_per_year": 250})
    hours_per_year = usage["hours_per_day"] * usage["days_per_year"]
    return lifecycle.expected_lifetime_years * hours_per_year


def check_lifecycle(
    version: DesignVersion,
    lifecycle: LifecycleModel,
    min_lifetime_hours: float = 5000.0,
    max_lifecycle_burden: float = 0.7
) -> Tuple[bool, str, float]:
    expected_lifetime_hours = estimate_expected_lifetime_hours(version, lifecycle)

    life_ok = expected_lifetime_hours >= min_lifetime_hours
    burden_ok = lifecycle.lifecycle_burden_index <= max_lifecycle_burden

    passed = life_ok and burden_ok
    reasons = []
    if not life_ok:
        reasons.append(f"expected_lifetime_hours={expected_lifetime_hours:.0f} < {min_lifetime_hours:.0f}")
    if not burden_ok:
        reasons.append(f"lifecycle_burden_index={lifecycle.lifecycle_burden_index:.2f} > {max_lifecycle_burden:.2f}")

    reason = "ok" if passed else "; ".join(reasons) or "lifecycle concerns"

    life_risk = max(0.0, (min_lifetime_hours - expected_lifetime_hours) / max(min_lifetime_hours, 1e-6))
    burden_risk = max(0.0, (lifecycle.lifecycle_burden_index - max_lifecycle_burden) / max(max_lifecycle_burden, 1e-6))
    risk = max(0.0, min(1.0, 0.5 * life_risk + 0.5 * burden_risk))

    return passed, reason, risk


def check_labor_ergonomics(
    labor: LaborProfile,
    max_total_production_hours: float = 500.0,
    allowed_ergonomic_flags: Optional[List[str]] = None
) -> Tuple[bool, str, float]:
    """
    If allowed_ergonomic_flags is None, ergonomics flags are informational only.
    If provided, then all ergonomics flags must be in the allowed set.
    """
    hours_ok = labor.total_production_hours <= max_total_production_hours

    if allowed_ergonomic_flags is None:
        ergonomics_ok = True
    else:
        ergonomics_ok = all(flag in allowed_ergonomic_flags for flag in labor.ergonomics_flags)

    passed = hours_ok and ergonomics_ok
    reasons = []
    if not hours_ok:
        reasons.append(f"total_production_hours={labor.total_production_hours:.1f} > {max_total_production_hours:.1f}")
    if not ergonomics_ok:
        reasons.append(f"ergonomic_flags={labor.ergonomics_flags} not all allowed")

    reason = "ok" if passed else "; ".join(reasons) or "labor/ergonomics concerns"

    hours_risk = max(0.0, (labor.total_production_hours - max_total_production_hours) / max(max_total_production_hours, 1e-6))
    ergonomics_risk = 1.0 if not ergonomics_ok else 0.0
    risk = max(0.0, min(1.0, 0.6 * hours_risk + 0.4 * ergonomics_risk))

    return passed, reason, risk


def check_integration(
    integration: IntegrationCheck,
    min_integration_score: float = 0.6
) -> Tuple[bool, str, float]:
    passed = integration.integration_score >= min_integration_score and not integration.conflicts

    reasons = []
    if integration.integration_score < min_integration_score:
        reasons.append(f"integration_score={integration.integration_score:.2f} < {min_integration_score:.2f}")
    if integration.conflicts:
        reasons.append(f"conflicts={integration.conflicts}")

    reason = "ok" if passed else "; ".join(reasons) or "integration concerns"

    score_risk = max(0.0, (min_integration_score - integration.integration_score) / max(min_integration_score, 1e-6))
    conflict_risk = min(1.0, 0.1 * len(integration.conflicts))
    risk = max(0.0, min(1.0, 0.7 * score_risk + 0.3 * conflict_risk))

    return passed, reason, risk
```

***

**2) Aggregate certification decision**

```python
def certify_design_version(
    version: DesignVersion,
    eco: EcoAssessment,
    lifecycle: LifecycleModel,
    labor: LaborProfile,
    sim: SimulationResult,
    integration: IntegrationCheck,
    certifiers: List[str],
    policy: Dict[str, Any],
) -> CertificationRecord:
    """
    OAD Module 9 — Validation, Certification & Release Manager
    ----------------------------------------------------------
    Apply policy thresholds and decide certification outcome.
    """

    eco_threshold = policy.get("eco_threshold", 0.5)
    max_risk_threshold = policy.get("max_risk_threshold", 0.5)
    min_feasibility = policy.get("min_feasibility", 0.7)
    min_yield_factor = policy.get("min_yield_factor", 1.2)
    min_lifetime_hours = policy.get("min_lifetime_hours", 5000.0)
    max_lifecycle_burden = policy.get("max_lifecycle_burden", 0.7)
    min_integration_score = policy.get("min_integration_score", 0.6)
    max_total_production_hours = policy.get("max_total_production_hours", 500.0)
    allowed_ergonomic_flags = policy.get("allowed_ergonomic_flags", None)

    criteria_passed: List[str] = []
    criteria_failed: List[str] = []
    risks: List[float] = []

    eco_ok, eco_reason, eco_risk = check_ecology(eco, max_eco_score=eco_threshold)
    (criteria_passed if eco_ok else criteria_failed).append(f"ecology: {eco_reason}")
    risks.append(eco_risk)

    saf_ok, saf_reason, saf_risk = check_safety_and_feasibility(
        sim, min_feasibility=min_feasibility, min_yield_factor=min_yield_factor
    )
    (criteria_passed if saf_ok else criteria_failed).append(f"safety_feasibility: {saf_reason}")
    risks.append(saf_risk)

    life_ok, life_reason, life_risk = check_lifecycle(
        version, lifecycle,
        min_lifetime_hours=min_lifetime_hours,
        max_lifecycle_burden=max_lifecycle_burden
    )
    (criteria_passed if life_ok else criteria_failed).append(f"lifecycle: {life_reason}")
    risks.append(life_risk)

    lab_ok, lab_reason, lab_risk = check_labor_ergonomics(
        labor,
        max_total_production_hours=max_total_production_hours,
        allowed_ergonomic_flags=allowed_ergonomic_flags
    )
    (criteria_passed if lab_ok else criteria_failed).append(f"labor_ergonomics: {lab_reason}")
    risks.append(lab_risk)

    int_ok, int_reason, int_risk = check_integration(integration, min_integration_score=min_integration_score)
    (criteria_passed if int_ok else criteria_failed).append(f"integration: {int_reason}")
    risks.append(int_risk)

    overall_risk = sum(risks) / len(risks) if risks else 0.0
    all_passed = eco_ok and saf_ok and life_ok and lab_ok and int_ok
    risk_ok = overall_risk <= max_risk_threshold

    if all_passed and risk_ok:
        version.status = "certified"
        status = "certified"
    else:
        # If criteria failed badly or risk too high, keep pending but route back to review
        version.status = "under_review"
        status = "pending" if risk_ok else "revoked"

    documentation_uri = generate_documentation_bundle(version.id)

    return CertificationRecord(
        version_id=version.id,
        certified_at=datetime.utcnow(),
        certified_by=certifiers,
        criteria_passed=criteria_passed,
        criteria_failed=criteria_failed,
        documentation_bundle_uri=documentation_uri,
        status=status,
    )
```

In practice, certification thresholds are sector-specific and policy-defined at the node or federation level (e.g., medical devices require stricter safety margins than garden tools).

**Math Sketch — Certification Risk Index**

Let the per-dimension risk scores be:
- $r_E$ = ecological risk
- $r_S$ = safety/feasibility risk
- $r_L$ = lifecycle risk
- $r_{Lab}$ = labor/ergonomic risk
- $r_I$ = integration risk

Define **overall risk**:

$$R_{\text{overall}} = \frac{1}{5}(r_E + r_S + r_L + r_{Lab} + r_I)$$

Certification decision:

$$\text{certify} = \begin{cases} \text{True}, & \text{if all dimension checks pass and } R_{\text{overall}} \le \tau_R \\ \text{False}, & \text{otherwise} \end{cases}$$

where $\tau_R$ is a conservatively chosen risk threshold (e.g. 0.5).

> Even if a design squeaks by on all individual checks, if its **aggregate risk profile** is too high, Module 9 can still refuse certification or demand redesign. This prevents "borderline" designs from slipping through just because they technically meet minimums.

---

**How Module 9 Feeds COS, ITC, and Module 10**

**COS**
- Only certified versions are treated as production-ready.
- COS queries CertificationRecords to assemble **approved design catalogs** for each sector and climate.

**ITC**
- Uses the certified bundle (Eco, Lifecycle, Labor, ValuationProfile) to compute:
  - access ITC ranges,
  - maintenance obligations,
  - and relative scarcity/impact signals.

**Module 10 (Knowledge Commons & Reuse Repository)**
- For every certified version, Module 9 passes:
  - `CertificationRecord`
  - `EcoAssessment`, `LifecycleModel`, `LaborProfile`, `SimulationResult`, `IntegrationCheck`
  - tags, climate, sector, and adoption data
- Module 10 then creates/updates `RepoEntry` and maintains reuse count and variant chains.
