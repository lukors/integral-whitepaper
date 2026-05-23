#### Module 9 (COS) — Transparency, Ledger & Audit

**Purpose**

Provide a **tamper-evident, queryable operational history** of production—labor, materials, throughput, failures, distribution, and coordination decisions. This history is the bridge that allows **ITC** and **FRS** to compute reality-based valuation, feedback, and long-term learning.

> *COS Module 9 records **what physically happened**. ITC Module 8 records **how access obligations were computed**. The two ledgers are linked, but not conflated.*

**Role in the System**

Upstream inputs (from COS Modules 1–8)

- Task lifecycle events (start, pause, completion)
- Labor participation (who worked, how long, skill tier)
- Material movements (reservation, consumption, recycling)
- Workflow state (WIP, bottlenecks, cycle time)
- QA outcomes (failures, severity, durability)
- Distribution events (personal, shared, repair, essential)
- Inter-coop coordination structure

Downstream consumers

- **ITC** — needs clean aggregates for valuation
   (labor by tier, material footprints, throughput realism)
- **FRS** — needs temporal traces and anomalies
   (defect spikes, ecological stress, dependency risk)
- **CDS & public** — need auditability for governance and trust

This is **not a blockchain**. It is:

- an append-only event stream,
- hash-chained for tamper evidence,
- human-readable,
- and purpose-built for cybernetic coordination.

***

**1. Types — Events, Ledger, Snapshots**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import hashlib
import json
from datetime import datetime
```

Event categories

```py
class COSEventType(str, Enum):
    LABOR = "labor"
    MATERIAL = "material"
    WORKFLOW = "workflow"
    QA = "qa"
    DISTRIBUTION = "distribution"
    COORDINATION = "coordination"
```

Base event

```python
@dataclass
class COSEvent:
    """
    Generic COS event. All production-relevant activity
    is represented as a sequence of these.
    """
    event_id: str
    event_type: COSEventType
    node_id: str
    coop_unit_id: str
    good_id: str
    version_id: str
    timestamp: datetime
    payload: Dict

    prev_hash: Optional[str] = None
    event_hash: Optional[str] = None
```

Hash utility

```python
def compute_event_hash(event: COSEvent) -> str:
    data = {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "node_id": event.node_id,
        "coop_unit_id": event.coop_unit_id,
        "good_id": event.good_id,
        "version_id": event.version_id,
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload,
        "prev_hash": event.prev_hash,
    }
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

Ledger container

```python
@dataclass
class COSLedger:
    """
    Append-only operational ledger for a node or cooperative unit.
    """
    node_id: str
    events: List[COSEvent] = field(default_factory=list)

    def append_event(self, event: COSEvent) -> COSEvent:
        if self.events:
            event.prev_hash = self.events[-1].event_hash
        event.event_hash = compute_event_hash(event)
        self.events.append(event)
        return event
```

***

**2. Event Payload Schemas (Conceptual)**

These are not rigid schemas—just shared meaning.

Labor event

```python
{
  "task_id": "frame_weld_step_03",
  "worker_id": "member_123",
  "hours": 2.5,
  "skill_tier": "high",
  "itc_weight_band": 1.6,
  "verified_by": "member_456",
  "itc_labor_event_id": "LE_abc123"
}
```

Material event

```python
{
  "material_id": "aluminum_tubing_6061",
  "quantity": 4.2,
  "unit": "kg",
  "direction": "consumed",
  "eii": 0.34
}
```

Workflow event

```python
{
  "task_id": "wheel_build",
  "state": "blocked",
  "reason": "missing_spokes",
  "wip_count": 5
}
```

QA event

```python
{
  "qa_batch_id": "bicycle_v3_batch_09",
  "sample_size": 10,
  "failures": 2,
  "failure_modes": ["spoke_tension", "paint_chip"],
  "severity_index": 0.4
}
```

Distribution event

```python
{
  "distribution_id": "dist_789",
  "channel": "shared_fleet",
  "quantity": 5,
  "itc_access_value": 42.0
}
```

Coordination event

```python
{
  "coordination_profile_id": "CP_bicycle_v3_nodeA",
  "autonomy_index": 0.78,
  "fragility_index": 0.21,
  "external_share": 0.12
}
```

***

**3. Ledger Integrity & Audit Checks**

```py
def verify_ledger_integrity(ledger: COSLedger) -> bool:
    """
    Verify hash-chain integrity of the COS ledger.
    """
    prev_hash = None
    for event in ledger.events:
        if event.prev_hash != prev_hash:
            return False
        if compute_event_hash(event) != event.event_hash:
            return False
        prev_hash = event.event_hash
    return True
```

***

**4. Aggregation for ITC — Production Summary**

```python
@dataclass
class ITCProductionSummary:
    good_id: str
    version_id: str
    node_id: str
    period_start: datetime
    period_end: datetime

    total_weighted_hours_by_tier: Dict[str, float] = field(default_factory=dict)
    total_raw_hours_by_tier: Dict[str, float] = field(default_factory=dict)

    material_consumption: Dict[str, float] = field(default_factory=dict)
    material_eii_weighted: Dict[str, float] = field(default_factory=dict)

    units_completed: int = 0
    units_failed_qa: int = 0
    avg_failure_severity: float = 0.0

def aggregate_for_itc(
    ledger: COSLedger,
    good_id: str,
    version_id: str,
    t_start: datetime,
    t_end: datetime,
) -> ITCProductionSummary:
    summary = ITCProductionSummary(
        good_id=good_id,
        version_id=version_id,
        node_id=ledger.node_id,
        period_start=t_start,
        period_end=t_end,
    )

    failure_severity_sum = 0.0
    failure_events = 0

    for ev in ledger.events:
        if ev.good_id != good_id or ev.version_id != version_id:
            continue
        if not (t_start <= ev.timestamp <= t_end):
            continue

        if ev.event_type == COSEventType.LABOR:
            tier = ev.payload.get("skill_tier", "unknown")
            hours = float(ev.payload.get("hours", 0.0))
            weight = float(ev.payload.get("itc_weight_band", 1.0))

            summary.total_raw_hours_by_tier[tier] = \
                summary.total_raw_hours_by_tier.get(tier, 0.0) + hours
            summary.total_weighted_hours_by_tier[tier] = \
                summary.total_weighted_hours_by_tier.get(tier, 0.0) + hours * weight

        elif ev.event_type == COSEventType.MATERIAL:
            if ev.payload.get("direction") == "consumed":
                mat = ev.payload.get("material_id")
                qty = float(ev.payload.get("quantity", 0.0))
                eii = float(ev.payload.get("eii", 0.0))

                summary.material_consumption[mat] = \
                    summary.material_consumption.get(mat, 0.0) + qty
                summary.material_eii_weighted[mat] = \
                    summary.material_eii_weighted.get(mat, 0.0) + qty * eii

        elif ev.event_type == COSEventType.QA:
            fails = int(ev.payload.get("failures", 0))
            severity = float(ev.payload.get("severity_index", 0.0))
            summary.units_failed_qa += fails
            failure_severity_sum += severity
            failure_events += 1

        elif ev.event_type == COSEventType.DISTRIBUTION:
            summary.units_completed += int(ev.payload.get("quantity", 0))

    if failure_events > 0:
        summary.avg_failure_severity = failure_severity_sum / failure_events

    return summary
```

***

**5. Aggregation for FRS — System Trace**

```python
@dataclass
class FRSProductionTrace:
    good_id: str
    version_id: str
    node_id: str
    period_start: datetime
    period_end: datetime

    total_units_completed: int
    total_units_failed_qa: int
    avg_failure_severity: float
    total_eii: float
    total_materials: Dict[str, float]

def build_frs_trace_from_itc_summary(
    summary: ITCProductionSummary
) -> FRSProductionTrace:
    return FRSProductionTrace(
        good_id=summary.good_id,
        version_id=summary.version_id,
        node_id=summary.node_id,
        period_start=summary.period_start,
        period_end=summary.period_end,
        total_units_completed=summary.units_completed,
        total_units_failed_qa=summary.units_failed_qa,
        avg_failure_severity=summary.avg_failure_severity,
        total_eii=sum(summary.material_eii_weighted.values()),
        total_materials=dict(summary.material_consumption),
    )
```

***

**6. Orchestration — Module 9 Pipeline**

```python
def run_cos_ledger_pipeline(
    ledger: COSLedger,
    good_id: str,
    version_id: str,
    t_start: datetime,
    t_end: datetime,
) -> Dict[str, object]:
    integrity_ok = verify_ledger_integrity(ledger)
    if not integrity_ok:
        raise ValueError("Ledger integrity check failed for node " + ledger.node_id)

    itc_summary = aggregate_for_itc(
        ledger=ledger,
        good_id=good_id,
        version_id=version_id,
        t_start=t_start,
        t_end=t_end,
    )

    frs_trace = build_frs_trace_from_itc_summary(itc_summary)

    return {
        "integrity_ok": integrity_ok,
        "itc_production_summary": itc_summary,
        "frs_production_trace": frs_trace,
    }
```

**Math Sketch — Conservation, Coverage, and Trust**

**1. Labor Conservation**

Weighted labor by skill tier $k$:

$$H_{\text{weighted}}^{(k)} = \sum_{e \in E_{\text{labor}}^{(k)}} h_e \cdot w_e$$

Total weighted labor across all skill tiers:

$$H_{\text{weighted}} = \sum_k H_{\text{weighted}}^{(k)}$$

This quantity **must match** (within tolerance) the labor cost used by ITC valuation. Any discrepancy indicates a data or logic error upstream.

---

**2. Material Footprint**

Total quantity of material $m$ consumed:

$$Q_m = \sum_{e \in E_{\text{material}}} q_{e,m}$$

Ecological impact for material $m$:

$$EII_m = \sum_{e \in E_{\text{material}}} q_{e,m} \cdot \mathrm{eii}_{e,m}$$

Aggregate ecological impact across all materials:

$$EII_{\text{total}} = \sum_m EII_m$$

This same aggregate must be used by **both ITC and FRS**, ensuring ecological consistency.

---

**3. QA Consistency**

Observed failure rate:

$$r_{\text{fail}} = \frac{U_{\text{failed}}}{U_{\text{completed}} + U_{\text{failed}}}$$

Deviation from projected failure rate triggers review:

$$\left| r_{\text{fail}} - r_{\text{proj}} \right| > \varepsilon \;\Rightarrow\; \text{trigger redesign or process review}$$

This is how **empirical reality corrects design assumptions**.

---

**4. Traceability**

Hash-chained event integrity:

$$h_i = H(e_i,\, h_{i-1})$$

Any modification to a prior event breaks all downstream hashes, making tampering **detectable rather than impossible**.

---

**Plain-Language Summary**

COS Module 9 ensures that **nothing important disappears into narrative fog**:
- every hour worked,
- every kilogram consumed,
- every failure,
- every distribution choice,

is recorded, chained, and auditable.

This allows Integral to compute value, fairness, and sustainability **from reality itself**, not from prices, authority, or trust claims.

