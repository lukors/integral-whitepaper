#### Module 4 (FRS) — Recommendation & Signal Routing Engine

**Purpose**
Transform `DiagnosticFinding` objects (FRS-2) and `ConstraintModel` outputs (FRS-3) into **typed, non-executive recommendations** and route them to the appropriate subsystem (**OAD, COS, ITC, CDS, FED**) without enforcing changes. Module 4 is the bridge from **intelligence → actionable signals**, while preserving distributed authority and democratic governance.

***

**Inputs**

- `DiagnosticFinding` objects (FRS-2)
- `ConstraintModel` objects (FRS-3), including scenario results + constraint breaches
- Optional `MemoryRecord` references (FRS-6) to suggest historically effective intervention patterns *(advisory only)*
- CDS-approved gating policy for what can be routed as:
  - a **technical alert** (non-normative, non-executive), vs.
  - a **CDS policy review prompt** (required visibility / deliberation)

***

**Outputs**

- `Recommendation` objects (typed + bounded, with rationale and evidence links)
- `RoutedSignal` objects (dispatch metadata: target, delivery status)

Recommendations are **not commands**. They are structured proposals that downstream systems can accept, reject, revise, or escalate through CDS.

***

**Core Logic **

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Assumes these types exist from the FRS high-level section:
# - DiagnosticFinding, ConstraintModel, ScenarioResult
# - Recommendation, RoutedSignal
# - Severity, FindingType, TargetSystem, RecommendationType
# - SemanticTag

# ---------------------------------------------------------
# CDS-approved gating policy (referenced by FRS; not authored here)
# ---------------------------------------------------------

SEVERITY_ORDER = ["info", "low", "moderate", "high", "critical"]

def severity_rank(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(s)
    except ValueError:
        return 0

@dataclass
class RecommendationPolicy:
    """
    Defines how FRS-4 gates recommendation visibility and routing.
    This is a referenced CDS policy object (versioned elsewhere).
    """
    require_cds_for_severity: List[str] = field(
        default_factory=lambda: ["high", "critical"]
    )

    require_cds_for_types: List[str] = field(
        default_factory=lambda: [
            "ecological_overshoot_risk",
            "access_inequity_detected",
            "proto_market_or_coercion_risk",
            "governance_overload_or_capture_risk",
        ]
    )

    allow_technical_routing: bool = True

    # Optional: mirror-to-CDS behavior for visibility even when routed elsewhere
    mirror_to_cds_when_routed: bool = True


def requires_cds_visibility(f: "DiagnosticFinding", policy: RecommendationPolicy) -> bool:
    return (
        f.severity in policy.require_cds_for_severity
        or f.finding_type in policy.require_cds_for_types
    )


# ---------------------------------------------------------
# Helper: pick reference scenarios for sensemaking payloads
# ---------------------------------------------------------

def pick_reference_scenarios(
    model: Optional["ConstraintModel"],
) -> Tuple[Optional["ScenarioResult"], Optional["ScenarioResult"]]:
    """
    Return (best, worst) scenario results by risk score.
    """
    if model is None or not model.scenario_results:
        return None, None
    best = min(model.scenario_results, key=lambda r: r.risk_score)
    worst = max(model.scenario_results, key=lambda r: r.risk_score)
    return best, worst


# ---------------------------------------------------------
# Recommendation template helpers (typed, bounded, non-executive)
# ---------------------------------------------------------

def make_cds_prompt(
    finding: "DiagnosticFinding",
    model: Optional["ConstraintModel"],
    summary: str,
    payload: Dict[str, Any],
    rationale: str,
) -> "Recommendation":
    return Recommendation(
        id=generate_id("rec"),
        node_id=finding.node_id,
        created_at=datetime.utcnow(),
        target_system="CDS",
        recommendation_type="policy_review_prompt",
        severity=finding.severity,
        confidence=finding.confidence,
        scope=finding.scope,
        related_findings=[finding.id],
        related_model_ids=[model.id] if model else [],
        tags=list(finding.related_tags),
        payload=payload,
        summary=summary,
        rationale=rationale,
    )


def recommend_for_ecological_overshoot(
    finding: "DiagnosticFinding",
    model: Optional["ConstraintModel"],
    policy: RecommendationPolicy,
) -> List["Recommendation"]:
    recs: List["Recommendation"] = []
    tags = list(finding.related_tags)

    best, worst = pick_reference_scenarios(model)

    # Always: CDS visibility prompt (normative thresholds/priorities)
    recs.append(make_cds_prompt(
        finding=finding,
        model=model,
        summary="Ecological overshoot risk approaching; CDS review of thresholds and provisioning priorities recommended.",
        payload={
            "finding_type": finding.finding_type,
            "key_indicators": finding.indicators,
            "scenario_best": best.summary if best else None,
            "scenario_worst": worst.summary if worst else None,
        },
        rationale=finding.rationale or finding.summary,
    ))

    if policy.allow_technical_routing:
        # OAD: substitution / durability / material intensity reduction
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="OAD",
            recommendation_type="material_substitution_prompt",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "goal": "reduce_material_drawdown_or_extend_lifespan",
                "candidate_materials_or_methods": ["lamination", "reclaimed_stock", "durable_coatings"],
                "notes": "Advisory prompt; redesign remains under OAD + CDS certification norms.",
            },
            summary="Prompt design/material strategies to restore regeneration margin (reduce drawdown or extend lifespan).",
            rationale="Near-binding ecological constraint detected; redesign/substitution may restore viability envelope.",
        ))

        # COS: waste/scrap + circular recovery attention
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="COS",
            recommendation_type="workflow_stress_alert",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "focus": ["scrap_rate", "repair_cycles", "material_recovery"],
                "notes": "Advisory alert; COS decides operational response under CDS constraints.",
            },
            summary="Flag production/material workflow for waste reduction and circular recovery optimization.",
            rationale="Reducing waste is the fastest non-coercive lever before scarcity becomes acute.",
        ))

    return recs


def recommend_for_quality_reliability_drift(
    finding: "DiagnosticFinding",
    model: Optional["ConstraintModel"],
    policy: RecommendationPolicy,
) -> List["Recommendation"]:
    recs: List["Recommendation"] = []
    tags = list(finding.related_tags)

    # OAD: design durability / lifecycle review
    if policy.allow_technical_routing:
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="OAD",
            recommendation_type="design_review_request",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "focus": "durability_and_maintenance_burden",
                "requested_outputs": ["updated_lifecycle_model", "maintenance_profile_revision"],
                "notes": "Advisory request; does not change certification status by itself.",
            },
            summary="Request design durability/maintainability review due to rising repair burden.",
            rationale=finding.rationale or finding.summary,
        ))

        # COS: workflow mitigation alerts
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="COS",
            recommendation_type="workflow_stress_alert",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "focus": ["drying_protocols", "corrosion_prevention", "rework_rate"],
                "notes": "Advisory; COS selects which workflow mitigations to trial.",
            },
            summary="Flag workflow adjustments to reduce environmental rework and corrosion stress.",
            rationale="Repair labor drift often indicates mismatch between design assumptions and field conditions.",
        ))

        # ITC: valuation drift flag (do not auto-change)
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="ITC",
            recommendation_type="valuation_drift_flag",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "signal": "maintenance_burden_increase_candidate",
                "notes": "Advisory flag; ITC adjustments remain bounded by CDS policy snapshots.",
            },
            summary="Flag valuation drift candidate due to increased maintenance burden.",
            rationale="Access obligations should reflect realized maintenance labor over time.",
        ))

    # If this finding is high/critical, add CDS visibility prompt
    if requires_cds_visibility(finding, policy) and policy.mirror_to_cds_when_routed:
        recs.append(make_cds_prompt(
            finding=finding,
            model=model,
            summary="Reliability drift detected; CDS visibility recommended (possible policy/priority implications).",
            payload={"finding_type": finding.finding_type, "indicators": finding.indicators},
            rationale=finding.rationale or finding.summary,
        ))

    return recs


def recommend_for_dependency_fragility_increase(
    finding: "DiagnosticFinding",
    model: Optional["ConstraintModel"],
    policy: RecommendationPolicy,
) -> List["Recommendation"]:
    recs: List["Recommendation"] = []
    tags = list(finding.related_tags)

    # CDS: dependency tolerance / autonomy strategy review
    recs.append(make_cds_prompt(
        finding=finding,
        model=model,
        summary="Dependency/fragility risk rising; CDS review of autonomy thresholds and transition priorities recommended.",
        payload={
            "finding_type": finding.finding_type,
            "indicator": finding.indicators,
        },
        rationale=finding.rationale or finding.summary,
    ))

    if policy.allow_technical_routing:
        # OAD: substitution/local production pathway prompts
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="OAD",
            recommendation_type="material_substitution_prompt",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "goal": "reduce_external_dependency",
                "candidate_pathways": ["bio-based polymers", "local binder production", "design to reduce resin need"],
                "notes": "Advisory; does not mandate sourcing changes.",
            },
            summary="Prompt substitution/local pathway exploration to reduce external dependency.",
            rationale="Dependency rise increases systemic fragility; redesign can reduce need or enable local pathways.",
        ))

        # COS: procurement stress alert (transitional external flagged)
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="COS",
            recommendation_type="dependency_risk_alert",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "action": "flag_transitional_external_procurement",
                "notes": "Advisory; COS may prioritize internal recycling/federated sourcing where feasible.",
            },
            summary="Flag procurement dependency risk; reduce external reliance where feasible.",
            rationale="Dependency drift is measurable; procurement strategy should align with resilience goals.",
        ))

        # ITC: valuation drift (dependency multiplier candidate, bounded and CDS-approved)
        recs.append(Recommendation(
            id=generate_id("rec"),
            node_id=finding.node_id,
            created_at=datetime.utcnow(),
            target_system="ITC",
            recommendation_type="valuation_drift_flag",
            severity=finding.severity,
            confidence=finding.confidence,
            scope="node",
            related_findings=[finding.id],
            related_model_ids=[model.id] if model else [],
            tags=tags,
            payload={
                "signal": "dependency_fragility_multiplier_candidate",
                "requires": "CDS_policy_bounds",
                "notes": "Advisory; apply only under CDS-approved caps and transparency rules.",
            },
            summary="Flag potential dependency/fragility multiplier candidate for access valuation (bounded).",
            rationale="If dependency increases systemic risk, valuation should reflect it transparently within bounds.",
        ))

    return recs


# ---------------------------------------------------------
# Main generator: findings + optional model -> recommendations
# ---------------------------------------------------------

def generate_recommendations(
    findings: List["DiagnosticFinding"],
    model: Optional["ConstraintModel"],
    policy: RecommendationPolicy,
) -> List["Recommendation"]:
    recs: List["Recommendation"] = []

    for f in findings:
        if f.finding_type == "ecological_overshoot_risk":
            recs.extend(recommend_for_ecological_overshoot(f, model, policy))
        elif f.finding_type == "quality_reliability_drift":
            recs.extend(recommend_for_quality_reliability_drift(f, model, policy))
        elif f.finding_type == "dependency_fragility_increase":
            recs.extend(recommend_for_dependency_fragility_increase(f, model, policy))
        else:
            # Generic routing: if CDS visibility is required, create a CDS prompt
            if requires_cds_visibility(f, policy):
                recs.append(make_cds_prompt(
                    finding=f,
                    model=model,
                    summary="System finding requires CDS visibility and review.",
                    payload={"finding_type": f.finding_type, "indicators": f.indicators},
                    rationale=f.rationale or f.summary,
                ))

    # Guardrail: ensure at least one CDS prompt exists for any high/critical finding
    if any(severity_rank(f.severity) >= severity_rank("high") for f in findings):
        if not any(r.target_system == "CDS" for r in recs):
            worst = max(findings, key=lambda x: severity_rank(x.severity))
            recs.append(make_cds_prompt(
                finding=worst,
                model=model,
                summary="High-severity risk present; CDS review required.",
                payload={"finding_type": worst.finding_type, "indicators": worst.indicators},
                rationale=worst.rationale or worst.summary,
            ))

    return recs


# ---------------------------------------------------------
# Routing / dispatch (non-executive)
# ---------------------------------------------------------

def route_recommendations(recs: List["Recommendation"]) -> List["RoutedSignal"]:
    routed: List["RoutedSignal"] = []
    for r in recs:
        routed.append(RoutedSignal(
            recommendation_id=r.id,
            target_system=r.target_system,
            dispatched_at=datetime.utcnow(),
            delivery_status="queued",
            notes="Dispatched by FRS-4 routing layer (non-executive).",
        ))
    return routed
```

***

**Running Example (Sailboat): From Model → Typed Recommendations**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how diagnosed findings and a constraint model are converted into typed, non-executive recommendations and routed to target subsystems.It introduces no new logic, rules, or authority beyond the formal specification above, and should be read strictly as an informative instantiation of the defined data structures—not as a procedural requirement, execution model, or prescriptive workflow.

```python
policy = RecommendationPolicy()

recs = generate_recommendations(
    findings=findings,   # from FRS-2 (sailboat drift + dependency + timber stress)
    model=model,         # from FRS-3 (scenario envelopes)
    policy=policy,
)

routed = route_recommendations(recs)

for r in recs:
    print(r.target_system, r.recommendation_type, r.severity, "-", r.summary)
```

Conceptually, you’ll see outputs like:

- **OAD**: design review request (durability + humidity resilience)
- **COS**: workflow stress alert (drying / corrosion prevention)
- **ITC**: valuation drift flags (maintenance burden, dependency multiplier candidate)
- **CDS**: policy review prompts (ecological threshold, dependency tolerance)

***

**Math Sketches**

**1. Recommendation as a Typed Function of Findings and Scenario Risk**

Let:
- $F$ be the set of diagnostic findings
- $M$ be an optional constraint model with scenario risk results
- $R$ be the set of recommendations produced

Module 4 computes:

$$R = g(F, M)$$

where $g$ is a bounded mapping that outputs **typed** recommendations with auditable payloads.

**2. Severity Gating for Democratic Review**

Let recommendation $r$ have severity $s(r)$.

Let $S_{CDS}$ be the severities requiring CDS visibility (e.g., $\{\text{high}, \text{critical}\}$).

If:

$$s(r) \in S_{CDS}$$

then CDS must receive a `policy_review_prompt` (directly or mirrored).

**3. Scenario Envelope as Evidence, Not Optimization**

Let $\text{risk}(s_i) \in [0,1]$ be modeled risk score for scenario $s_i$.

FRS-4 can support a recommendation by referencing:

$$\Delta = \text{risk}(\text{status quo}) - \text{risk}(\text{combined intervention})$$

A large $\Delta$ increases confidence in the relevance of the recommendation, but does not create executive authority.

---

**Plain-Language Summary**

FRS Module 4 turns diagnosis and modeling into **clear, typed recommendations**—and routes them to the systems that can respond—without executing changes. It keeps authority distributed: COS adjusts workflows, OAD revises designs, ITC recalibrates valuation within bounds, and CDS remains the only place norms and policy are decided.
