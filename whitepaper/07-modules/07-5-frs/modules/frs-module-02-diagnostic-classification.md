#### Module 2 (FRS) — Diagnostic Classification & Pathology Detection

**Purpose**

Detect and classify emerging system stresses by distinguishing **causes vs. symptoms**, assigning **severity, scope, persistence, and confidence**, and emitting structured **DiagnosticFindings** for modeling (FRS-3) and routing (FRS-4).

***

**Inputs**

Module 2 consumes:

- `SignalPacket` objects (from FRS-1)
- Optional baseline references from `MemoryRecord` (FRS-6), used only to contextualize deviation
- CDS-approved diagnostic configuration references (thresholds, scopes, persistence windows) that FRS **references** but does not author

***

**Outputs**

Module 2 produces:

- `DiagnosticFinding` objects, each with:
  - `finding_type`, `severity`, `scope`, `persistence`, `confidence`
  - `evidence_refs` (packet/envelope IDs, ledger IDs if relevant)
  - `indicators` (computed margins, deltas, ratios)
  - `summary` + `rationale` (audit-ready)
- Optional “finding index” keyed by tags/domains for downstream lookup

***

**Core Logic **

```python

from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

# ----------------------------
# Metric helpers
# ----------------------------

def get_metric(packet: SignalPacket, metric_name: str, default: Optional[float] = None) -> Optional[float]:
    """
    Retrieve the first matching metric value from a SignalPacket.
    (Aggregation strategy is simplified here for clarity.)
    """
    for env in packet.envelopes:
        for m in env.metrics:
            if m.name == metric_name:
                return float(m.value)
    return default


def pct_delta(current: float, baseline: float, eps: float = 1e-6) -> float:
    """Percent delta: +0.18 means +18%."""
    return (current - baseline) / max(abs(baseline), eps)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ----------------------------
# CDS-approved threshold references
# ----------------------------

@dataclass
class DiagnosticThresholds:
    """
    Thresholds are referenced by FRS but authored and versioned by CDS.
    """
    timber_regen_margin_min_kg_week: float = 0.0
    repair_hours_delta_warn: float = 0.10
    repair_hours_delta_crit: float = 0.25

    dependency_ratio_warn: float = 1.3
    dependency_ratio_crit: float = 2.0

    humidity_high_pct: float = 80.0
    min_persistence_windows_emerging: int = 2
    min_persistence_windows_persistent: int = 4


def classify_persistence(hits: int, th: DiagnosticThresholds) -> Persistence:
    if hits >= th.min_persistence_windows_persistent:
        return "persistent"
    if hits >= th.min_persistence_windows_emerging:
        return "emerging"
    return "transient"


def classify_severity_from_delta(d: float, warn: float, crit: float) -> Severity:
    if d >= crit:
        return "critical"
    if d >= warn:
        return "moderate"
    if d > 0:
        return "low"
    return "info"


def compute_sailboat_indicators(current: SignalPacket, baseline: Optional[SignalPacket]) -> Dict[str, float]:
    """
    Produce explicit indicators used to classify DiagnosticFindings.
    """
    timber_use = get_metric(current, "timber_consumed_kg_week", 0.0) or 0.0
    timber_regen = get_metric(current, "timber_regeneration_kg_week", 0.0) or 0.0
    humidity = get_metric(current, "humidity_pct", 0.0) or 0.0
    salinity = get_metric(current, "salinity_index", 0.0) or 0.0

    repair_hours = get_metric(current, "repair_labor_hours_week", 0.0) or 0.0
    external_resin = get_metric(current, "external_resin_procured_kg_week", 0.0) or 0.0
    internal_resin = get_metric(current, "internal_resin_available_kg_week", 0.0) or 0.0

    baseline_repair = repair_hours
    baseline_timber = timber_use
    if baseline:
        baseline_repair = get_metric(baseline, "repair_labor_hours_week", repair_hours) or repair_hours
        baseline_timber = get_metric(baseline, "timber_consumed_kg_week", timber_use) or timber_use

    return {
        "timber_use_kg_week": timber_use,
        "timber_regen_kg_week": timber_regen,
        "timber_margin_kg_week": (timber_regen - timber_use),
        "humidity_pct": humidity,
        "salinity_index": salinity,

        "repair_hours_week": repair_hours,
        "repair_hours_delta_pct": pct_delta(repair_hours, baseline_repair),

        "external_internal_resin_ratio": external_resin / max(internal_resin, 1e-6),
        "timber_use_delta_pct": pct_delta(timber_use, baseline_timber),
    }


def diagnose_sailboat_packet(
    current: SignalPacket,
    baseline: Optional[SignalPacket],
    thresholds: DiagnosticThresholds,
    persistence_hits: Dict[str, int],
) -> List[DiagnosticFinding]:
    """
    Produce DiagnosticFindings from the current SignalPacket, using baseline
    only for deviation context and CDS threshold references for classification.
    """
    node_id = current.node_id
    inds = compute_sailboat_indicators(current, baseline)

    findings: List[DiagnosticFinding] = []
    evidence_refs = [current.id] + [e.id for e in current.envelopes]
    tags = [SemanticTag("good_id", "sailboat_shared_v1")]

    # 1) Ecological overshoot risk (timber margin)
    margin = inds["timber_margin_kg_week"]
    if margin < thresholds.timber_regen_margin_min_kg_week:
        key = "ecological_overshoot_risk"
        hits = persistence_hits.get(key, 0) + 1
        persistence_hits[key] = hits

        sev_score = clamp(abs(margin) / 80.0, 0.0, 1.0)
        severity: Severity = "critical" if sev_score >= 0.75 else ("moderate" if sev_score >= 0.25 else "low")

        findings.append(DiagnosticFinding(
            id=generate_id("finding"),
            node_id=node_id,
            finding_type="ecological_overshoot_risk",
            severity=severity,
            scope="node",
            persistence=classify_persistence(hits, thresholds),
            confidence="medium",
            detected_at=datetime.utcnow(),
            related_tags=tags + [SemanticTag("material_id", "timber_marine_grade")],
            evidence_refs=evidence_refs,
            indicators=inds,
            summary="Timber drawdown risk detected (consumption exceeds regeneration).",
            rationale=f"timber_margin_kg_week={margin:.1f} (regen - use).",
        ))

    # 2) Reliability / maintenance drift (repair-hours delta)
    repair_delta = inds["repair_hours_delta_pct"]
    if repair_delta > 0.0:
        key = "quality_reliability_drift"
        hits = persistence_hits.get(key, 0) + 1
        persistence_hits[key] = hits

        severity = classify_severity_from_delta(
            repair_delta,
            thresholds.repair_hours_delta_warn,
            thresholds.repair_hours_delta_crit,
        )

        findings.append(DiagnosticFinding(
            id=generate_id("finding"),
            node_id=node_id,
            finding_type="quality_reliability_drift",
            severity=severity,
            scope="node",
            persistence=classify_persistence(hits, thresholds),
            confidence="high",
            detected_at=datetime.utcnow(),
            related_tags=tags,
            evidence_refs=evidence_refs,
            indicators=inds,
            summary="Maintenance labor drift detected (repair hours rising vs baseline).",
            rationale=f"repair_hours_delta_pct={repair_delta*100:.1f}%.",
        ))

    # 3) Dependency / fragility increase (resin ratio)
    dep_ratio = inds["external_internal_resin_ratio"]
    if dep_ratio >= thresholds.dependency_ratio_warn:
        key = "dependency_fragility_increase"
        hits = persistence_hits.get(key, 0) + 1
        persistence_hits[key] = hits

        severity = "critical" if dep_ratio >= thresholds.dependency_ratio_crit else "moderate"

        findings.append(DiagnosticFinding(
            id=generate_id("finding"),
            node_id=node_id,
            finding_type="dependency_fragility_increase",
            severity=severity,
            scope="node",
            persistence=classify_persistence(hits, thresholds),
            confidence="medium",
            detected_at=datetime.utcnow(),
            related_tags=tags + [SemanticTag("material_id", "marine_resin")],
            evidence_refs=evidence_refs,
            indicators=inds,
            summary="External dependency risk rising (marine resin reliance increasing).",
            rationale=f"external_internal_resin_ratio={dep_ratio:.2f}.",
        ))

    # 4) Contextual amplifier (humidity + salinity)
    if inds["humidity_pct"] >= thresholds.humidity_high_pct and inds["salinity_index"] >= 0.7:
        findings.append(DiagnosticFinding(
            id=generate_id("finding"),
            node_id=node_id,
            finding_type="other",
            severity="low",
            scope="local",
            persistence="emerging",
            confidence="medium",
            detected_at=datetime.utcnow(),
            related_tags=tags + [SemanticTag("context", "coastal_corrosion_pressure")],
            evidence_refs=evidence_refs,
            indicators=inds,
            summary="Coastal corrosion pressure elevated (humidity + salinity high).",
            rationale=f"humidity_pct={inds['humidity_pct']:.1f}, salinity_index={inds['salinity_index']:.2f}.",
        ))

    return findings
```

***

**Running Example (Sailboat): Packet → Findings**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how already structured, upstream-generated packets are diagnosed and classified by FRS-2. It introduces no new logic, rules, or authority beyond the formal specification above, and should be read strictly as an informative instantiation of the defined data structures—not as a procedural requirement, execution model, or prescriptive workflow.

```python
thresholds = DiagnosticThresholds(
    timber_regen_margin_min_kg_week=0.0,
    repair_hours_delta_warn=0.10,
    repair_hours_delta_crit=0.25,
    dependency_ratio_warn=1.3,
    dependency_ratio_crit=2.0,
    humidity_high_pct=80.0,
)

persistence_hits = {}  # rolling state (stored by FRS state/memory layer)

findings = diagnose_sailboat_packet(
    current=current_packet,
    baseline=baseline_packet,
    thresholds=thresholds,
    persistence_hits=persistence_hits,
)

for f in findings:
    print(f.finding_type, f.severity, f.persistence, f.summary)
```

Expected conceptual outputs:

- ecological overshoot risk (timber margin)
- reliability drift (repair labor rising)
- dependency risk (resin reliance increasing)
- contextual corrosion pressure (supporting finding)

***

**Math Sketches**

**1. Drift / Deviation**

Let $x_t$ be a current metric and $x_0$ a baseline:

$$\Delta_{\text{pct}} = \frac{x_t - x_0}{\lvert x_0 \rvert + \epsilon}$$

**2. Persistence**

Let a finding type trigger in $k$ out of the last $N$ windows:

$$\text{persistence} = \begin{cases} \text{persistent}, & k \ge k_p \\ \text{emerging}, & k \ge k_e \\ \text{transient}, & \text{otherwise} \end{cases}$$

**3. Ecological Margin Test**

For regenerative resources:

$$\text{margin} = R - C$$

If $\text{margin} < 0$ and persists, overshoot risk increases.

***

**Plain-Language Summary**

FRS Module 2 turns "a lot of signals" into "a few named problems":
- it classifies drift into **typed findings** (ecology, reliability, dependency, etc.),
- it attaches **severity, scope, persistence, and confidence**,
- and it produces auditable objects that downstream modules can model and route—without FRS prescribing or executing anything.
