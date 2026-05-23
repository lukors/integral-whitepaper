#### Module 6 (FRS) — Longitudinal Memory, Pattern Learning & Institutional Recall

**Purpose**
Preserve, structure, and operationalize institutional memory so Integral can learn across time without ossifying. Module 6 ensures that past conditions, interventions, and outcomes remain **queryable evidence**, not ideology—enabling future diagnosis, modeling, and governance to avoid repeating mistakes and to recognize proven solution patterns.

FRS-6 does not decide what should be repeated. It records what happened, under what conditions, and with what consequences.

***

**Inputs**

- `DiagnosticFinding` objects (FRS-2)
- `ConstraintModel` + `ScenarioResult` objects (FRS-3)
- `Recommendation` objects and CDS outcomes (accepted, rejected, modified)
- COS execution summaries, QA outcomes, ITC valuation shifts (via ledgers / trace logs)
- Ecological and operational traces over time (FRS-1 packets)
- Optional inter-node memory shares (FRS-7)

***

**Outputs**

Durable `MemoryRecord` objects representing:

- **baselines** (pre-intervention state)
- **incidents** (detected drift or stress)
- **interventions** (what was tried)
- **outcomes** (measured effects)
- **lessons** (generalized patterns, explicitly confidence-scored)

Recall utilities / indexes for:

- “similar past conditions”
- “what worked / what failed”
- “side-effects and tradeoffs”

Structured inputs for:

- FRS-3 (priors + parameter tuning)
- FRS-4 (recommendation templates)
- FRS-5 (historical parallels in deliberation)

***

**Design Principles**

1. **Non-prescriptive memory**
    Records facts and outcomes, not mandates or “best practices.”
2. **Contextual specificity**
    Every record is tagged with ecological, material, social, and temporal context.
3. **Versioned truth**
    Memory is additive and revisable—new outcomes do not erase old ones.
4. **Pattern extraction, not dogma**
    Generalizations are explicit, bounded, and confidence-scored.

***

**Core Logic **

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import math

# Assumes these exist from the FRS high-level types:
# - MemoryRecord, MemoryRecordType, SemanticTag
# - DiagnosticFinding, ConstraintModel, Recommendation
# - generate_id(...)

# ---------------------------------------------------------
# Similarity helper (indicator-vector cosine similarity)
# ---------------------------------------------------------

def cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """
    Compute cosine similarity between two indicator vectors.
    """
    keys = set(a.keys()) & set(b.keys())
    if not keys:
        return 0.0

    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(a[k] ** 2 for k in keys))
    norm_b = math.sqrt(sum(b[k] ** 2 for k in keys))
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# ---------------------------------------------------------
# Memory construction
# ---------------------------------------------------------

def build_memory_record(
    node_id: str,
    record_type: "MemoryRecordType",
    title: str,
    tags: List["SemanticTag"],
    evidence_refs: List[str],
    narrative: str,
    quantified_state: Optional[Dict[str, float]] = None,
    quantified_outcomes: Optional[Dict[str, float]] = None,
    related_decisions: Optional[List[str]] = None,
    related_design_versions: Optional[List[str]] = None,
) -> "MemoryRecord":
    """
    Create a durable MemoryRecord.
    We store both:
      - quantified_state: indicators describing the situation ("what conditions looked like")
      - quantified_outcomes: measurable deltas after intervention ("what changed")
    """
    return MemoryRecord(
        id=generate_id("memory"),
        node_id=node_id,
        created_at=datetime.utcnow(),
        record_type=record_type,
        title=title,
        tags=tags,
        evidence_refs=evidence_refs,
        related_decisions=related_decisions or [],
        related_design_versions=related_design_versions or [],
        narrative=narrative,
        quantified_outcomes={
            **(quantified_state or {}),
            **(quantified_outcomes or {}),
        },
        notes="Recorded by FRS-6 for longitudinal recall and learning.",
    )


# ---------------------------------------------------------
# Recording a full learning episode (incident → intervention → outcome → lesson)
# ---------------------------------------------------------

def record_learning_episode(
    node_id: str,
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    recommendations: List["Recommendation"],
    cds_outcomes: Dict[str, str],                 # recommendation_id -> "accepted"/"rejected"/"modified"
    state_indicators: Dict[str, float],           # snapshot of the problem-state at time of detection
    outcome_deltas: Dict[str, float],             # measured deltas after intervention
    related_decision_ids: Optional[List[str]] = None,
) -> List["MemoryRecord"]:
    """
    Convert a resolved FRS episode into memory records.
    """
    records: List["MemoryRecord"] = []

    # Merge tags from findings + recommendations for indexing
    tags: List["SemanticTag"] = []
    for f in findings:
        tags.extend(f.related_tags)

    accepted = [r for r in recommendations if cds_outcomes.get(r.id) == "accepted"]

    # 1) Baseline record (what conditions looked like at detection time)
    records.append(build_memory_record(
        node_id=node_id,
        record_type="baseline",
        title="Baseline state at detection time",
        tags=tags,
        evidence_refs=[f.id for f in findings] + ([model.id] if model else []),
        narrative="State indicators captured at time of drift detection for later comparison.",
        quantified_state=state_indicators,
        quantified_outcomes={},
        related_decisions=related_decision_ids,
    ))

    # 2) Incident record (what FRS classified)
    records.append(build_memory_record(
        node_id=node_id,
        record_type="incident",
        title="Detected drift / stress episode",
        tags=tags,
        evidence_refs=[f.id for f in findings],
        narrative="FRS classified a multi-signal drift episode with severity/scope/persistence labels.",
        quantified_state=state_indicators,
        quantified_outcomes={},
        related_decisions=related_decision_ids,
    ))

    # 3) Intervention record (what was approved/attempted)
    if accepted:
        records.append(build_memory_record(
            node_id=node_id,
            record_type="intervention",
            title="Intervention package approved by CDS",
            tags=tags,
            evidence_refs=[r.id for r in accepted],
            narrative="CDS approved a bounded intervention package (design/workflow/training/dependency actions).",
            quantified_state=state_indicators,
            quantified_outcomes={},
            related_decisions=related_decision_ids,
        ))

    # 4) Outcome record (what changed measurably)
    records.append(build_memory_record(
        node_id=node_id,
        record_type="outcome",
        title="Observed outcomes after intervention window",
        tags=tags,
        evidence_refs=[model.id] if model else [],
        narrative="Measured outcome deltas captured after the intervention window.",
        quantified_state=state_indicators,
        quantified_outcomes=outcome_deltas,
        related_decisions=related_decision_ids,
    ))

    # 5) Lesson record (explicitly non-prescriptive pattern)
    # Note: Confidence scoring happens separately; this is just a candidate lesson.
    records.append(build_memory_record(
        node_id=node_id,
        record_type="lesson",
        title="Candidate lesson pattern (non-prescriptive)",
        tags=tags + [SemanticTag("pattern", "coastal_humidity_resilience")],
        evidence_refs=[r.id for r in accepted] if accepted else [],
        narrative=(
            "In coastal conditions, durability drift linked to humidity/salinity was mitigated most effectively "
            "through material substitution and workflow sequencing changes. This is evidence, not a mandate."
        ),
        quantified_state=state_indicators,
        quantified_outcomes=outcome_deltas,
        related_decisions=related_decision_ids,
    ))

    return records


# ---------------------------------------------------------
# Recall: retrieve past cases with similar state indicators
# ---------------------------------------------------------

def recall_similar_cases(
    memory_records: List["MemoryRecord"],
    current_state_indicators: Dict[str, float],
    min_similarity: float = 0.6,
    allowed_record_types: Optional[List[str]] = None,
) -> List[Tuple["MemoryRecord", float]]:
    """
    Retrieve past cases with similar *state* indicator profiles.
    """
    allowed = set(allowed_record_types or ["baseline", "incident"])
    matches: List[Tuple["MemoryRecord", float]] = []

    for r in memory_records:
        if r.record_type not in allowed:
            continue
        sim = cosine_similarity(current_state_indicators, r.quantified_outcomes)
        if sim >= min_similarity:
            matches.append((r, sim))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


# ---------------------------------------------------------
# Pattern confidence (optional, non-prescriptive)
# ---------------------------------------------------------

def pattern_confidence(
    deltas: List[float],
    min_n: int = 3,
) -> float:
    """
    Very simple confidence sketch:
    - more episodes + consistent improvement => higher confidence.
    """
    n = len(deltas)
    if n < min_n:
        return 0.2  # low confidence due to small sample

    avg = sum(deltas) / n
    var = sum((d - avg) ** 2 for d in deltas) / max(1, n - 1)

    # Higher avg improvement and lower variance => higher confidence
    score = 0.5 * (1.0 / (1.0 + var)) + 0.5 * max(0.0, min(1.0, avg))
    return max(0.0, min(1.0, score))
```

***

**Running Example (Sailboat): “We’ve Seen This Before”**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how a resolved FRS episode is recorded into longitudinal memory, and how similar future conditions can retrieve evidence from past cases. It introduces no new logic, rules, or authority beyond the formal specification above, and should be read strictly as an informative instantiation of the defined data structures—not as a procedural requirement, execution model, or prescriptive workflow.

```python
state_indicators = {
    "repair_hours_delta_pct": 0.18,
    "external_internal_resin_ratio": 1.6,
    "timber_margin_kg_week": -20.0,
    "humidity_pct": 82.0,
    "salinity_index": 0.74,
}

outcome_deltas = {
    "repair_hours_delta_pct": -0.22,          # 22% reduction vs baseline
    "external_internal_resin_ratio": -0.45,   # 45% reduction
    "timber_margin_kg_week": +35.0,           # margin restored
}

cds_outcomes = {r.id: "accepted" for r in recs if r.target_system != "CDS"}

records = record_learning_episode(
    node_id="node_coastal_A",
    findings=findings,
    model=model,
    recommendations=recs,
    cds_outcomes=cds_outcomes,
    state_indicators=state_indicators,
    outcome_deltas=outcome_deltas,
    related_decision_ids=["cds_decision_123"],
)

# Months later: a new node sees similar humidity-linked drift.
similar = recall_similar_cases(
    memory_records=records,
    current_state_indicators=state_indicators,
    min_similarity=0.6,
)

for rec, sim in similar:
    print(rec.record_type, sim, rec.title)
```

Conceptual takeaway:
A later node gets “we saw this pattern before” as **evidence** (what conditions matched, what interventions were tried, what outcomes occurred)—not as an order.

***

**Math Sketches**

**1. Similarity-Based Recall**

Let current state indicator vector be $\mathbf{x}$ and a past record's stored indicator vector be $\mathbf{y}$.

Define cosine similarity:

$$\mathrm{sim}(\mathbf{x},\mathbf{y})=\frac{\mathbf{x}\cdot\mathbf{y}}{\|\mathbf{x}\|\,\|\mathbf{y}\|}$$

Recall records where:

$$\mathrm{sim}(\mathbf{x},\mathbf{y}) \ge \tau$$

where $\tau$ is a configurable threshold.

---

**2. Pattern Confidence Accumulation**

Let a pattern $p$ appear in $n$ episodes with measurable improvement deltas $\Delta_1,\dots,\Delta_n$.

A simple confidence proxy:

$$\mathrm{conf}(p)=h(n,\overline{\Delta},\mathrm{var}(\Delta))$$

where $h(\cdot)$ increases with sample size and average improvement, and decreases with variance. Higher confidence increases prominence in FRS-4/5 artifacts—but never becomes mandatory.

---

**3. Anti-Dogma Safeguard**

Memory does not imply correctness:

$$\text{Memory evidence} \neq \text{Policy authority}$$

FRS-6 outputs remain inputs to modeling and deliberation, not executive decisions.

---

**Plain-Language Summary**

FRS Module 6 ensures Integral doesn't "solve" the same problem repeatedly. It records what conditions looked like, what actions were taken, and what outcomes followed—so future nodes can recall comparable cases as evidence. Memory informs modeling and democratic choice, but never replaces it.
