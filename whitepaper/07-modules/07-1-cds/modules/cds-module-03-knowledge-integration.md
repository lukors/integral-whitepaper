#### Module 3 (CDS) — Knowledge Integration & Context Engine

**Purpose**

Module 3 aggregates all relevant knowledge—submitted evidence, historical records, ecological constraints, resource and labor data, past decisions, and system-generated signals—into an organized contextual substrate that later modules (4–6) can reason about.

It is the cognitive **“memory + analysis layer”** of CDS. Where Module 2 structures the *shape* of public reasoning, Module 3 ensures the system has a complete and accurate **information environment** for evaluating scenarios responsibly.

**Inputs**

- `StructuredIssueView` (clusters + themes from Module 2)
- Evidence submissions (from Module 1 / `Issue.submissions`)
- Contextual system data:
  - FRS ecological metrics and risk signals
  - COS capacity, labor windows, resource availability
  - ITC fairness constraints and weighting context
- Historical decisions and rationale logs
- External datasets (e.g., climate, hydrology, geospatial layers, safety codes)

**Outputs**

- A `ContextModel` containing consolidated, queryable indicators:
  - ecological limits and risk exposures
  - resource and labor constraints
  - historical precedent and comparable past outcomes
  - social/fairness considerations
  - dependency couplings and infrastructural interactions
- Updated issue lifecycle state:
  - `issue.status = "context_ready"`
  - `issue.last_updated_at` set

This becomes the input for **Module 4 (Norms & Constraint Checking)** and **Module 5 (Participatory Deliberation Workspace)**.

***

**Helper Type (for context layer)**

```python
from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass
class ContextModel:
    issue_id: str
    ecological: Dict[str, Any]            # thresholds, footprints, risk metrics
    resources: Dict[str, Any]             # materials, tooling, bottlenecks
    labor: Dict[str, Any]                 # capacity windows, skills, constraints
    historical: List[Dict[str, Any]]      # similar past decisions + outcomes
    dependencies: Dict[str, Any]          # couplings with other infrastructure
    social: Dict[str, Any]                # accessibility, equity signals
    evidence_index: List[Dict[str, Any]]  # structured evidence pointers + summaries
    metadata: Dict[str, Any]
```

(Note: `ContextModel` is a computed context layer, not a permanent CDS record.)

***

**Core Logic**

```python
from datetime import datetime
from typing import Dict, List, Any

def extract_evidence_submissions(issue: Issue) -> List[Submission]:
    """
    Pull evidence submissions from Module 1 intake.
    Evidence is not clustered in Module 2; it is indexed here.
    """
    return [s for s in issue.submissions if s.type == "evidence"]


def index_evidence(evidence_submissions: List[Submission]) -> List[Dict[str, Any]]:
    """
    Build a light evidence index: pointers, tags, short summaries.
    This is not full document processing—just a contextual scaffold.
    """
    indexed = []
    for s in evidence_submissions:
        indexed.append({
            "submission_id": s.id,
            "author_id": s.author_id,
            "created_at": s.created_at.isoformat(),
            "tags": s.metadata.get("tags", []),
            "source": s.metadata.get("source", "member"),
            "link": s.metadata.get("link"),
            "summary": s.metadata.get("summary") or (s.content[:200] + "..." if len(s.content) > 200 else s.content),
        })
    return indexed


def build_context_model(
    issue: Issue,
    structured: StructuredIssueView,
    frs_data: Dict[str, Any],
    cos_data: Dict[str, Any],
    itc_data: Dict[str, Any],
    historical_records: List[Dict[str, Any]],
    external_datasets: Dict[str, Any],
) -> ContextModel:
    """
    Module 3 — Knowledge Integration & Context Engine
    -------------------------------------------------
    Aggregates contextual information relevant to an Issue
    so Modules 4–6 can evaluate feasibility, limits, and consequences.

    Note: Module 3 builds context; it does not decide.
    """
    now = datetime.utcnow()

    # 1) Evidence indexing (from Module 1 submissions)
    evidence_subs = extract_evidence_submissions(issue)
    evidence_idx = index_evidence(evidence_subs)

    # 2) Context extraction from system sources
    ecological_signals = extract_ecological_indicators(structured, frs_data, external_datasets)
    resource_profile   = extract_resource_metrics(structured, cos_data)
    labor_profile      = extract_labor_capacity(structured, cos_data)
    fairness_profile   = extract_fairness_signals(itc_data)

    # 3) Historical matching + dependency mapping
    historical_links = match_to_historical_precedent(issue, historical_records, structured)
    dependency_graph = map_system_dependencies(issue, cos_data, frs_data, external_datasets)

    context = ContextModel(
        issue_id=issue.id,
        ecological=ecological_signals,
        resources=resource_profile,
        labor=labor_profile,
        historical=historical_links,
        dependencies=dependency_graph,
        social=fairness_profile,
        evidence_index=evidence_idx,
        metadata={
            "source_modules": ["FRS", "COS", "ITC"],
            "external_sources_present": list(external_datasets.keys()),
            "num_clusters": len(structured.clusters),
            "num_evidence_items": len(evidence_idx),
            "built_at": now.isoformat(),
        }
    )

    # Update issue lifecycle state (consistent with updated CDS types)
    issue.status = "context_ready"
    issue.last_updated_at = now

    return context
```

***

**What Module 3 Actually Computes**

- **Ecological layer:** emissions proxies, material footprints, water use, waste streams, risk exposure
- **Resource layer:** tooling/material availability, fabrication limits, external procurement dependency
- **Labor layer:** skill requirements, availability windows, likely bottlenecks
- **Social/fairness layer:** accessibility impacts, protected-category considerations, distributional effects
- **Historical layer:** outcomes of similar past decisions, failure patterns, precedent constraints
- **Evidence index:** structured pointers to submitted sources, links, and summaries

Everything is organized so downstream modules can evaluate **what is actually possible and responsible**.

***

**Math Sketch — Multi-Criteria Indicator Aggregation**

Module 3 often needs to normalize heterogeneous indicators so that Modules 4–6 can reason about them systematically.

Let:
- $E_j$ = ecological indicators
- $R_j$ = resource indicators
- $L_j$ = labor indicators
- $S_j$ = social/fairness indicators

Normalize each using min–max scaling:

$$x'_j = \frac{x_j - \min(x_j)}{\max(x_j) - \min(x_j)}$$

Then build a context score vector:

$$\mathbf{C} = \left[ \alpha_E \mathbf{E}',\; \alpha_R \mathbf{R}',\; \alpha_L \mathbf{L}',\; \alpha_S \mathbf{S}' \right]$$

where the $\alpha$ coefficients are **not chosen by Module 3**, but derived from CDS constitutional settings, ecological thresholds, COS capacity constraints, and ITC fairness bounds. This yields a usable representation of **context saturation** that Modules 4–6 can test proposals against.
