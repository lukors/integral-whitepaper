#### Module 7 (COS) — Quality Assurance & Safety Verification

**Purpose**

Validate that produced goods actually meet their **performance, safety, durability, and maintainability targets**, and turn real test results into structured signals for **OAD** (redesign), **ITC** (valuation), and **FRS** (system health).

**Role in the system**

Upstream modules produce expectations:

- **OAD** predicted: “This unit should last $X$ years, require $Y$ maintenance, tolerate $Z$ loads.”
- **COS 1–6** executed production and routed units into access channels.
- **ITC** computed initial access obligations based on expected labor, lifecycle, and ecology.

Module 7 asks the blunt question:

> “Did reality match the model?”

If not, it:

- flags defects and safety risks,
- updates the effective lifecycle/maintenance expectations,
- and emits bounded signals that can raise or lower **future** access obligations (and optionally differentiate specific batches).

***

**Types — QA Specs, Results, and Signals**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
from datetime import datetime
import math
import random

class QATestType(str, Enum):
    FUNCTIONAL = "functional"               # works as intended?
    SAFETY = "safety"                       # safe under limits / fails safely?
    DURABILITY = "durability"               # wear, fatigue, stress over time
    MAINTAINABILITY = "maintainability"     # repair time / ease
    ECO_COMPLIANCE = "eco_compliance"       # toxicity, emissions, residues, etc.

@dataclass
class QATestSpec:
    """
    Design-time QA definition for a given good/version.
    Typically originates in OAD, optionally refined by COS/FRS.
    """
    good_id: str
    version_id: str
    tests: Dict[QATestType, Dict]           # per-test params (sample_fraction, thresholds, etc.)
    expected_unit_failure_rate: float       # expected fraction of units that fail (0–1)
    expected_lifespan_hours: float          # from OAD lifecycle model
    expected_maintenance_hours: float       # per unit over lifecycle

@dataclass
class QATestResult:
    """
    Result of a specific QA test run on a single unit.
    """
    unit_id: str
    test_type: QATestType
    passed: bool
    metrics: Dict[str, float]               # test-specific metrics, may include repair_time_hours
    notes: str = ""

@dataclass
class QABatchSummary:
    """
    Aggregated QA view for a batch of units.
    Important: distinguish unit-level failure rates from test-level failure rates.
    """
    good_id: str
    version_id: str
    node_id: str
    batch_id: str

    total_units: int
    tested_units: int

    # Diagnostics by test type (counts of failed test runs)
    failed_tests_by_type: Dict[QATestType, int]

    # Unit-level outcomes (units that failed at least one critical test)
    failed_unit_ids: Set[str] = field(default_factory=set)
    severe_safety_failed_unit_ids: Set[str] = field(default_factory=set)

    # Rates (bounded 0–1)
    unit_failure_rate: float = 0.0          # failed_units / tested_units
    test_failure_rate: float = 0.0          # failed_tests / total_tests_run

    avg_repair_time_hours: float = 0.0      # from MAINTAINABILITY tests when present
    notes: str = ""

@dataclass
class ITCReliabilitySignal:
    """
    How QA results should influence valuation parameters for this good/version in this node.
    """
    good_id: str
    version_id: str
    node_id: str
    batch_id: str

    observed_unit_failure_rate: float
    expected_unit_failure_rate: float

    suggested_lifespan_multiplier: float        # multiply OAD expected lifespan
    suggested_maintenance_multiplier: float     # multiply OAD expected maintenance hours
    suggested_access_multiplier: float          # bounded, optional adjustment to access obligation

    notes: str = ""

@dataclass
class FRSFailureSignal:
    """
    System-level view for FRS: are failures/safety/ecology deviating?
    """
    good_id: str
    version_id: str
    node_id: str
    batch_id: str

    unit_failure_rate: float
    severe_safety_failures: int
    eco_noncompliance_count: int

    description: str
```

***

**Core Logic**

1) Sampling

```python
def select_qa_sample(unit_ids: List[str], sample_fraction: float, min_samples: int = 1) -> List[str]:
    n_total = len(unit_ids)
    n_sample = max(min_samples, int(math.ceil(sample_fraction * n_total)))
    n_sample = min(n_sample, n_total)
    return random.sample(unit_ids, n_sample)
```

2) Test execution placeholder

```python
def run_qa_test_on_unit(unit_id: str, test_type: QATestType, test_params: Dict) -> QATestResult:
    """
    Placeholder QA executor. Real systems call instruments, rigs, sensors, labs.
    Here: a simple probabilistic pass/fail plus optional maintainability metrics.
    """
    base_fail_prob = float(test_params.get("base_fail_prob", 0.02))
    roll = random.random()
    passed = roll > base_fail_prob

    metrics: Dict[str, float] = {"random_roll": roll}

    # Optional: emit repair time estimates for maintainability tests
    if test_type == QATestType.MAINTAINABILITY:
        # rough placeholder: lower is better
        mean = float(test_params.get("mean_repair_time_hours", 0.75))
        jitter = float(test_params.get("repair_time_jitter", 0.25))
        metrics["repair_time_hours"] = max(0.05, random.uniform(mean - jitter, mean + jitter))

    return QATestResult(unit_id=unit_id, test_type=test_type, passed=passed, metrics=metrics)
```

3) Run QA for a batch

```python
def run_qa_for_batch(
    good_id: str,
    version_id: str,
    node_id: str,
    batch_id: str,
    unit_ids: List[str],
    qa_spec: QATestSpec,
) -> List[QATestResult]:
    results: List[QATestResult] = []

    for test_type, params in qa_spec.tests.items():
        sample_fraction = float(params.get("sample_fraction", 0.2))
        sample_units = select_qa_sample(unit_ids, sample_fraction)

        for u in sample_units:
            results.append(run_qa_test_on_unit(u, test_type, params))

    return results
```

4) Summarize QA results

Critical change: we compute **unit-level failures** separately from **test-level failures**.

```python
def summarize_qa_results(
    good_id: str,
    version_id: str,
    node_id: str,
    batch_id: str,
    unit_ids: List[str],
    qa_results: List[QATestResult],
    critical_test_types: Optional[set] = None,
) -> QABatchSummary:
    """
    Aggregate QA test results for a batch.
    - failed_tests_by_type: counts failed *test runs*
    - failed_unit_ids: units that failed at least one critical test
    """
    critical_test_types = critical_test_types or {QATestType.FUNCTIONAL, QATestType.SAFETY}

    tested_units_set = {r.unit_id for r in qa_results}
    tested_units = len(tested_units_set)
    total_units = len(unit_ids)

    failed_tests_by_type: Dict[QATestType, int] = {}
    failed_unit_ids: Set[str] = set()
    severe_safety_failed_unit_ids: Set[str] = set()

    repair_times: List[float] = []
    total_tests_run = len(qa_results)
    total_failed_tests = 0

    for r in qa_results:
        if not r.passed:
            total_failed_tests += 1
            failed_tests_by_type[r.test_type] = failed_tests_by_type.get(r.test_type, 0) + 1

            if r.test_type in critical_test_types:
                failed_unit_ids.add(r.unit_id)

            if r.test_type == QATestType.SAFETY:
                severe_safety_failed_unit_ids.add(r.unit_id)

        if r.test_type == QATestType.MAINTAINABILITY and "repair_time_hours" in r.metrics:
            repair_times.append(float(r.metrics["repair_time_hours"]))

    unit_failure_rate = (len(failed_unit_ids) / max(tested_units, 1)) if tested_units > 0 else 0.0
    test_failure_rate = (total_failed_tests / max(total_tests_run, 1)) if total_tests_run > 0 else 0.0

    avg_repair_time = (sum(repair_times) / len(repair_times)) if repair_times else 0.0

    return QABatchSummary(
        good_id=good_id,
        version_id=version_id,
        node_id=node_id,
        batch_id=batch_id,
        total_units=total_units,
        tested_units=tested_units,
        failed_tests_by_type=failed_tests_by_type,
        failed_unit_ids=failed_unit_ids,
        severe_safety_failed_unit_ids=severe_safety_failed_unit_ids,
        unit_failure_rate=unit_failure_rate,
        test_failure_rate=test_failure_rate,
        avg_repair_time_hours=avg_repair_time,
        notes="Aggregated QA summary (unit-level + test-level failure rates).",
    )
```

***

5) Translate QA deviations into ITC signals

```python
def build_itc_reliability_signal(
    qa_spec: QATestSpec,
    qa_summary: QABatchSummary,
    epsilon: float = 1e-6,
    beta: float = 0.5,
    gamma: float = 0.5,
    eta: float = 0.3,
    alpha_L_min: float = 0.3,
    alpha_L_max: float = 1.2,
    alpha_M_min: float = 0.8,
    alpha_M_max: float = 2.0,
    m_min: float = 0.7,
    m_max: float = 1.5,
) -> ITCReliabilitySignal:
    """
    Use QA deviations to propose adjustments to lifespan, maintenance,
    and (optionally) access obligations for this good.
    """
    p0 = float(qa_spec.expected_unit_failure_rate)
    phat = float(qa_summary.unit_failure_rate)

    r_p = (phat + epsilon) / (p0 + epsilon)

    alpha_L = 1.0 / (r_p ** beta)
    alpha_L = max(alpha_L_min, min(alpha_L_max, alpha_L))

    alpha_M = r_p ** gamma
    alpha_M = max(alpha_M_min, min(alpha_M_max, alpha_M))

    m = 1.0 + eta * (r_p - 1.0)
    m = max(m_min, min(m_max, m))

    notes = (
        f"QA unit_failure_rate={phat:.4f} vs expected={p0:.4f}; "
        f"ratio={r_p:.3f}; lifespan_mult={alpha_L:.3f}; "
        f"maintenance_mult={alpha_M:.3f}; access_mult={m:.3f}."
    )

    return ITCReliabilitySignal(
        good_id=qa_summary.good_id,
        version_id=qa_summary.version_id,
        node_id=qa_summary.node_id,
        batch_id=qa_summary.batch_id,
        observed_unit_failure_rate=phat,
        expected_unit_failure_rate=p0,
        suggested_lifespan_multiplier=alpha_L,
        suggested_maintenance_multiplier=alpha_M,
        suggested_access_multiplier=m,
        notes=notes,
    )p
```

***

6) FRS failure signal

```python
def build_frs_failure_signal(qa_summary: QABatchSummary) -> FRSFailureSignal:
    eco_noncompliance = qa_summary.failed_tests_by_type.get(QATestType.ECO_COMPLIANCE, 0)
    severe_safety_failures = len(qa_summary.severe_safety_failed_unit_ids)

    desc = (
        f"QA batch {qa_summary.batch_id} ({qa_summary.good_id}, node {qa_summary.node_id}): "
        f"unit_failure_rate={qa_summary.unit_failure_rate:.3f}, "
        f"severe_safety_failed_units={severe_safety_failures}, "
        f"eco_noncompliance_tests={eco_noncompliance}."
    )

    return FRSFailureSignal(
        good_id=qa_summary.good_id,
        version_id=qa_summary.version_id,
        node_id=qa_summary.node_id,
        batch_id=qa_summary.batch_id,
        unit_failure_rate=qa_summary.unit_failure_rate,
        severe_safety_failures=severe_safety_failures,
        eco_noncompliance_count=eco_noncompliance,
        description=desc,
    )
```

***

7) Orchestration: Full Module 7 pass

```python
def run_quality_assurance_pipeline(
    good_id: str,
    version_id: str,
    node_id: str,
    batch_id: str,
    unit_ids: List[str],
    qa_spec: QATestSpec,
) -> Dict[str, object]:
    """
    COS Module 7 — Quality Assurance & Safety Verification
    ------------------------------------------------------
    1) Run QA tests on a batch sample.
    2) Summarize results (unit-level + test-level).
    3) Emit ITC reliability signal.
    4) Emit FRS failure signal.
    """
    qa_results = run_qa_for_batch(
        good_id=good_id,
        version_id=version_id,
        node_id=node_id,
        batch_id=batch_id,
        unit_ids=unit_ids,
        qa_spec=qa_spec,
    )

    summary = summarize_qa_results(
        good_id=good_id,
        version_id=version_id,
        node_id=node_id,
        batch_id=batch_id,
        unit_ids=unit_ids,
        qa_results=qa_results,
    )

    itc_signal = build_itc_reliability_signal(qa_spec=qa_spec, qa_summary=summary)
    frs_signal = build_frs_failure_signal(summary)

    return {
        "qa_results": qa_results,
        "qa_summary": summary,
        "itc_reliability_signal": itc_signal,
        "frs_failure_signal": frs_signal,
    }
```

***

**Math Sketch — QA-driven valuation adjustment**

Let:
- $p_0$ = expected **unit** failure rate (design-time)
- $\hat{p}$ = observed **unit** failure rate (QA/field)
- $L_0$ = expected lifespan hours
- $M_0$ = expected maintenance hours over lifecycle

Failure ratio:

$$
r_p = \frac{\hat{p} + \epsilon}{p_0 + \epsilon}
$$

Suggested lifespan multiplier:

$$
\alpha_L = \mathrm{clip}\left(\frac{1}{r_p^\beta},\ \alpha_{L,\min},\ \alpha_{L,\max}\right)
$$

Suggested maintenance multiplier:

$$
\alpha_M = \mathrm{clip}\left(r_p^\gamma,\ \alpha_{M,\min},\ \alpha_{M,\max}\right)
$$

Optional access multiplier (bounded):

$$
m = \mathrm{clip}\left(1 + \eta(r_p - 1),\ m_{\min},\ m_{\max}\right)
$$

Interpretation:
- If $\hat{p} > p_0$, then $r_p > 1$: lifespan decreases, maintenance increases, access obligation can rise modestly.
- If $\hat{p} < p_0$, then $r_p < 1$: durability is better than expected; access obligations can drift downward over time.

***

**Plain-language summary**

Module 7 is where **design claims meet empirical reality**. If a product fails early, proves unsafe, or demands more maintenance than predicted, COS logs it and produces clean signals:
- **OAD** gets redesign triggers,
- **FRS** gets systemic alerts,
- **ITC** gets bounded reliability adjustments so access obligations reflect real lifecycle burden—without markets, profit, or speculation.
