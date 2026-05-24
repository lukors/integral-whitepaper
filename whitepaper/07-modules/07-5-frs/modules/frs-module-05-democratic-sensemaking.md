#### Module 5 (FRS)— Democratic Sensemaking & CDS Interface

**Purpose**
Translate FRS findings, models, and routed recommendations into **human-comprehensible sensemaking artifacts**—dashboards, risk briefs, scenario comparisons, and deliberation prompts—so that CDS can govern with shared situational awareness rather than technical opacity.

FRS-5 does **not** decide. It renders reality legible for democratic process.

***

**Inputs**

- `DiagnosticFinding` objects (FRS-2)
- `ConstraintModel` objects + `ScenarioResult`s (FRS-3)
- `Recommendation` objects + routing metadata (FRS-4)
- Optional `MemoryRecord` references for “historical parallels” (FRS-6) *(context only; never overrides evidence)*
- Optional CDS context: current deliberation queues, policy snapshots, and audience configuration *(what level of detail is appropriate)*

***

**Outputs**

- `SensemakingArtifact` objects such as:
  - `risk_brief` (executive summary + key indicators)
  - `scenario_comparison` (status quo vs interventions)
  - `dashboard_view` (trend panels + constraint margins)
  - `deliberation_prompt` (structured questions + tradeoffs)
  - `public_summary` (high-level transparency layer)

Artifacts are **auditable**: each includes links back to the exact findings/models/recommendations that generated it.

***

**Core Logic **

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Assumes these types exist from the FRS high-level section:
# - DiagnosticFinding, ConstraintModel, ScenarioResult
# - Recommendation, SensemakingArtifact
# - Constraint, SemanticTag
# - generate_id(...)
# Also reuses pick_reference_scenarios(model) from FRS-4.

SEVERITY_ORDER = ["info", "low", "moderate", "high", "critical"]

def severity_rank(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(s)
    except ValueError:
        return 0


# ---------------------------------------------------------
# Helper: summarize findings + constraints for human readers
# ---------------------------------------------------------

def summarize_findings(findings: List["DiagnosticFinding"], max_items: int = 5) -> List[Dict[str, Any]]:
    """
    Build a compact human-readable summary list.
    Sorted by severity (critical > high > ... > info), then persistence.
    """
    persistence_order = {"structural": 3, "persistent": 2, "emerging": 1, "transient": 0}

    sorted_findings = sorted(
        findings,
        key=lambda f: (severity_rank(f.severity), persistence_order.get(f.persistence, 0)),
        reverse=True
    )

    out: List[Dict[str, Any]] = []
    for f in sorted_findings[:max_items]:
        # Keep indicators compact; CDS can drill down via evidence refs
        keys = list(f.indicators.keys())[:6]
        out.append({
            "finding_type": f.finding_type,
            "severity": f.severity,
            "persistence": f.persistence,
            "scope": f.scope,
            "confidence": f.confidence,
            "summary": f.summary,
            "key_indicators": {k: f.indicators.get(k) for k in keys},
            "evidence_refs": f.evidence_refs[:6],
        })
    return out


def summarize_constraints(constraints: List["Constraint"]) -> List[Dict[str, Any]]:
    """
    Turn constraints into a margin-oriented table for dashboards.
    """
    rows: List[Dict[str, Any]] = []
    for c in constraints:
        rows.append({
            "name": c.name,
            "domain": c.domain,
            "direction": c.direction,
            "threshold": c.threshold,
            "current_value": c.current_value,
            "margin": c.margin,
            "unit": c.unit,
            "confidence": c.confidence,
            "tags": [(t.key, t.value) for t in c.tags],
        })
    return rows


def scenario_table(model: "ConstraintModel") -> List[Dict[str, Any]]:
    """
    Compact scenario comparison rows (sorted by risk).
    """
    rows: List[Dict[str, Any]] = []
    for r in model.scenario_results:
        rows.append({
            "scenario_id": r.scenario_id,
            "horizon": r.horizon,
            "risk_score": r.risk_score,
            "constraint_breaches": r.constraint_breaches,
            "projected_metrics": r.projected_metrics,
        })
    rows.sort(key=lambda x: x["risk_score"])
    return rows


# ---------------------------------------------------------
# Prompts: convert technical outputs into CDS questions
# ---------------------------------------------------------

def build_deliberation_prompts(
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    recs: List["Recommendation"],
) -> List[str]:
    """
    Generate structured questions for CDS deliberation.
    These are prompts, not prescriptions.
    """
    prompts: List[str] = []

    types = {f.finding_type for f in findings}

    if "ecological_overshoot_risk" in types:
        prompts.append(
            "Ecology: Do we revise provisioning priorities or accelerate redesign/substitution "
            "to restore the regeneration margin before thresholds are breached?"
        )

    if "dependency_fragility_increase" in types:
        prompts.append(
            "Autonomy: Do we prioritize reducing external dependency via local capacity building, "
            "federated sourcing, or OAD substitution pathways?"
        )

    if "quality_reliability_drift" in types:
        prompts.append(
            "Durability: Do we prioritize design changes, workflow mitigations, or accept higher maintenance "
            "burden temporarily while transitioning?"
        )

    if model:
        best, worst = pick_reference_scenarios(model)
        if best and worst:
            prompts.append(
                f"Scenario envelope: lowest-risk is '{best.scenario_id}' (risk={best.risk_score:.2f}), "
                f"highest-risk is '{worst.scenario_id}' (risk={worst.risk_score:.2f}). "
                "Which path best matches current labor/material capacity and constitutional priorities?"
            )

    targets = {r.target_system for r in recs}
    if "OAD" in targets:
        prompts.append("Design: Do we authorize an OAD design sprint (timebox, success criteria, test plan)?")
    if "COS" in targets:
        prompts.append("Operations: Do we authorize COS workflow changes now within existing constraints?")
    if "ITC" in targets:
        prompts.append("Valuation: Do we request ITC to recompute access-values after updated OAD/COS data is validated?")

    # Always: uncertainty acknowledgement
    prompts.append(
        "Uncertainty: Which assumptions are most uncertain here, and what monitoring would reduce uncertainty fastest?"
    )

    return prompts


# ---------------------------------------------------------
# Artifact builders
# ---------------------------------------------------------

def build_risk_brief(
    node_id: str,
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    recs: List["Recommendation"],
) -> "SensemakingArtifact":
    """
    Short executive summary: what is happening, why it matters, what paths exist.
    """
    content: Dict[str, Any] = {
        "top_findings": summarize_findings(findings, max_items=5),
        "recommendations": [
            {"target": r.target_system, "type": r.recommendation_type, "severity": r.severity, "summary": r.summary}
            for r in recs
        ],
        "viability_envelope": None,
        "notes": [
            "FRS provides evidence and scenario envelopes; CDS retains normative authority.",
            "These artifacts are decision-support, not executive directives.",
        ],
    }

    if model:
        best, worst = pick_reference_scenarios(model)
        content["viability_envelope"] = {
            "constraint_margins": summarize_constraints(model.constraints),
            "best_scenario": {
                "scenario_id": best.scenario_id,
                "risk_score": best.risk_score,
                "breaches": best.constraint_breaches,
                "projected_metrics": best.projected_metrics,
            } if best else None,
            "worst_scenario": {
                "scenario_id": worst.scenario_id,
                "risk_score": worst.risk_score,
                "breaches": worst.constraint_breaches,
                "projected_metrics": worst.projected_metrics,
            } if worst else None,
        }

    return SensemakingArtifact(
        id=generate_id("artifact"),
        node_id=node_id,
        created_at=datetime.utcnow(),
        artifact_type="risk_brief",
        title="FRS Risk Brief — Current Drift and Viability Envelope",
        audience="cds_participants",
        related_findings=[f.id for f in findings],
        related_recommendations=[r.id for r in recs],
        related_models=[model.id] if model else [],
        content=content,
        summary="Executive summary of drift patterns, constraint margins, and recommended focus areas.",
    )


def build_scenario_comparison(
    node_id: str,
    model: "ConstraintModel",
) -> "SensemakingArtifact":
    """
    Scenario table comparing intervention envelopes (not predictions).
    """
    content: Dict[str, Any] = {
        "scenario_rows": scenario_table(model),
        "constraints": summarize_constraints(model.constraints),
        "notes": "Scenarios represent counterfactual envelopes, not forecasts or commands.",
    }

    return SensemakingArtifact(
        id=generate_id("artifact"),
        node_id=node_id,
        created_at=datetime.utcnow(),
        artifact_type="scenario_comparison",
        title="FRS Scenario Comparison — Viability Envelopes by Horizon",
        audience="cds_participants",
        related_findings=list(model.related_findings),
        related_recommendations=[],
        related_models=[model.id],
        content=content,
        summary="Scenario envelopes comparing risk and constraint breaches across intervention options.",
    )


def build_deliberation_prompt_artifact(
    node_id: str,
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    recs: List["Recommendation"],
) -> "SensemakingArtifact":
    """
    Structured prompts for CDS discussion.
    """
    prompts = build_deliberation_prompts(findings, model, recs)

    content: Dict[str, Any] = {
        "prompts": prompts,
        "ground_rules": [
            "FRS provides evidence and scenarios; CDS retains normative authority.",
            "Express preferences alongside constraints (labor, ecology, resilience).",
            "State uncertainty explicitly; avoid false precision.",
        ],
        "traceability": {
            "findings": [f.id for f in findings],
            "models": [model.id] if model else [],
            "recommendations": [r.id for r in recs],
        },
    }

    return SensemakingArtifact(
        id=generate_id("artifact"),
        node_id=node_id,
        created_at=datetime.utcnow(),
        artifact_type="deliberation_prompt",
        title="FRS Deliberation Prompts — Questions for Democratic Resolution",
        audience="cds_participants",
        related_findings=[f.id for f in findings],
        related_recommendations=[r.id for r in recs],
        related_models=[model.id] if model else [],
        content=content,
        summary="Structured questions to help CDS resolve tradeoffs using shared situational awareness.",
    )


# ---------------------------------------------------------
# Main module orchestrator
# ---------------------------------------------------------

def build_sensemaking_artifacts(
    node_id: str,
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    recs: List["Recommendation"],
) -> List["SensemakingArtifact"]:
    """
    FRS-5: produce a small bundle of CDS-ready artifacts.
    """
    artifacts: List["SensemakingArtifact"] = []

    # Always produce: risk brief + deliberation prompts
    artifacts.append(build_risk_brief(node_id, findings, model, recs))
    artifacts.append(build_deliberation_prompt_artifact(node_id, findings, model, recs))

    # If scenario model exists, also produce scenario comparison
    if model is not None:
        artifacts.append(build_scenario_comparison(node_id, model))

    return artifacts
```

***

**Running Example (Sailboat): “Make It Legible for CDS”**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how FRS-2 findings, an FRS-3 constraint model, and FRS-4 recommendations are translated into CDS-ready sensemaking artifacts by FRS-5. It introduces no new logic, rules, or authority beyond the formal specification above, and should be read strictly as an informative instantiation of the defined data structures—not as a procedural requirement, execution model, or prescriptive workflow.

```python
artifacts = build_sensemaking_artifacts(
    node_id="node_coastal_A",
    findings=findings,   # drift + dependency + timber stress
    model=model,         # scenario envelopes
    recs=recs,           # typed non-executive recommendations
)

for a in artifacts:
    print(a.artifact_type, "-", a.title)
```

Typical outputs for the sailboat case:

- **Risk Brief:** “Timber drawdown risk emerging; maintenance drift rising; resin dependency increasing.”
- **Scenario Comparison:** “Status quo breaches constraints in mid/long horizon; combined intervention restores viability envelope.”
- **Deliberation Prompts:** “Authorize OAD sprint? Adjust COS workflow now? Prioritize autonomy strategy? Revisit thresholds?”

***

**Math Sketches**

**1. Ranking and Salience in Democratic Presentation**

FRS-5 must prioritize what humans can realistically deliberate.

Let each finding $f_i$ have severity $s_i$, persistence $p_i$, and confidence $c_i$, mapped to numeric scales.

Define a salience score:

$$\text{salience}(f_i) = w_s s_i + w_p p_i + w_c c_i$$

Then present the top-$k$ findings by salience, rather than dumping full telemetry into governance.

**2. Scenario Comparison as a Viability Envelope**

Let each scenario $s$ yield risk $\rho(s)$ and breach set $B(s)$.

FRS-5 does not "choose the minimum"; it shows:
- $\rho(\text{status quo})$ versus $\rho(\text{interventions})$
- how $B(s)$ changes by horizon
- which constraints become binding first

This frames governance as **tradeoff selection under constraints**, not preference voting in a vacuum.

**3. Explainability Constraint**

Every artifact must remain traceable back to source evidence:

$$\text{artifact} \Rightarrow \{\text{findings},\ \text{models},\ \text{recommendations},\ \text{evidence refs}\}$$

This prevents technocratic opacity: CDS can always inspect the chain of reasoning.

***

**Plain-Language Summary**

FRS Module 5 ensures that cybernetic intelligence doesn't become technocratic fog. It turns findings, models, and recommendations into clear, auditable artifacts—so CDS deliberates with a shared picture of reality: what is drifting, what constraints are tightening, what futures are plausible, and what tradeoffs are actually on the table.
