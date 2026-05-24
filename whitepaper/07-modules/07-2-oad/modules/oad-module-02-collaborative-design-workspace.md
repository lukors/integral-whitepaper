#### Module 2 (OAD) — Collaborative Design Workspace

**Purpose**

Enable transparent, iterative, multi-user refinement of designs via branching, merging, and tracked changes—turning a single structured submission into an evolving family of design variants.

**Role in the System**

This module is the social and technical engine of design evolution. It provides:

- version-controlled design branches
- collaborative edits and annotations
- transparent change histories
- a basis for selecting promising variants for deeper assessment (ecology, lifecycle, labor, feasibility, integration, optimization)

Module 2 does not decide which design is “best.” It creates the structured design landscape that downstream modules (3–10) will evaluate and, in some cases, feed back into.

**Design reuse and local adaptation also occur here.**
Certified designs retrieved from the **Knowledge Commons (Module 10)** re-enter the workspace as new branches, allowing nodes to adapt designs to local materials, climates, constraints, and infrastructure while preserving lineage.

**Inputs**

- Existing `DesignSpec` and one or more `DesignVersion` objects
- New contributions from participants (geometry edits, material changes, parameter tweaks, notes)
- Optional metrics from downstream modules (e.g., eco scores from Module 3, feasibility scores from Module 5)
- **Reuse inputs**: a certified `DesignVersion` pulled from Module 10 for local adaptation

**Outputs**

- New `DesignVersion` branches
- Updated `DesignVersion` objects with refined parameters and change logs
- Traceable version history (parent–child relationships via `parent_version_id` and `VERSION_CHILDREN`)

***

**Core Logic**

We assume a simple in-memory registry (in practice this would be a database or distributed store):

```python
from typing import Dict, List, Optional, Any
from datetime import datetime

# Illustrative in-memory registries
DESIGN_SPECS: Dict[str, DesignSpec] = {}
DESIGN_VERSIONS: Dict[str, DesignVersion] = {}
VERSION_CHILDREN: Dict[str, List[str]] = {}  # parent_version_id -> [child_version_ids]
```

**Creating a New Branch (local variation, material swap, adaptation)**

```python
def create_design_branch(
    base_version_id: str,
    author_id: str,
    label_suffix: str,
    param_updates: Dict[str, Any],
    material_updates: Optional[List[str]] = None,
    cad_file_updates: Optional[List[str]] = None,  # URIs/hashes for updated geometry
    change_note: str = "",
) -> DesignVersion:
    """
    OAD Module 2 — Collaborative Design Workspace
    ---------------------------------------------
    Create a new branch (child DesignVersion) from an existing version.

    This is how one proposal becomes a design 'family':
    different materials, geometries, or local adaptations.
    """
    base = DESIGN_VERSIONS[base_version_id]

    # Copy and update parameters
    new_params = dict(base.parameters)
    new_params.update(param_updates)

    # Materials: either updated or inherited from base
    new_materials = material_updates if material_updates is not None else list(base.materials)

    # CAD references: either updated or inherited (real CAD merges handled externally)
    new_cad_files = cad_file_updates if cad_file_updates is not None else list(base.cad_files)

    new_version = DesignVersion(
        id=generate_id("version"),
        spec_id=base.spec_id,
        parent_version_id=base_version_id,
        label=f"{base.label}-{label_suffix}",
        created_at=datetime.utcnow(),
        authors=list(set(base.authors + [author_id])),
        cad_files=new_cad_files,
        materials=new_materials,
        parameters=new_params,
        change_log=change_note or f"Branch from {base.label} by {author_id}",
        status="draft",
        superseded_by_version_id=None,
    )

    DESIGN_VERSIONS[new_version.id] = new_version
    VERSION_CHILDREN.setdefault(base_version_id, []).append(new_version.id)

    return new_version
```

**Updating an Existing Version (collaborative edit)**

```python
def update_design_version(
    version_id: str,
    author_id: str,
    param_updates: Dict[str, Any],
    change_note: str,
    cad_file_updates: Optional[List[str]] = None,
) -> DesignVersion:
    """
    Apply incremental refinements to an existing design version.
    Suitable for small, non-breaking changes in geometry/parameters.
    """
    v = DESIGN_VERSIONS[version_id]

    # Update parameters in place (or this could spawn a micro-revision)
    new_params = dict(v.parameters)
    new_params.update(param_updates)
    v.parameters = new_params

    # Optional: update CAD references (actual CAD diffs handled externally)
    if cad_file_updates is not None:
        v.cad_files = cad_file_updates

    if author_id not in v.authors:
        v.authors.append(author_id)

    v.change_log += f"\n[{datetime.utcnow().isoformat()}] {author_id}: {change_note}"
    return v
```

**Reuse Import Helper (Module 10 → Module 2 entry)**

```python
def import_from_commons_for_local_adaptation(
    certified_version_id: str,
    author_id: str,
    local_context_tag: str,
    param_updates: Dict[str, Any],
    change_note: str,
) -> DesignVersion:
    """
    Treat a certified design pulled from Module 10 as the base for a local
    adaptation branch, preserving full lineage and traceability.
    """
    return create_design_branch(
        base_version_id=certified_version_id,
        author_id=author_id,
        label_suffix=f"adapted-{local_context_tag}",
        param_updates=param_updates,
        material_updates=None,
        cad_file_updates=None,
        change_note=change_note,
    )
```

***

**Simple Branch Preference Helper (Using Downstream Scores)**

```
def choose_preferred_branch(
    version_a_id: str,
    version_b_id: str,
    eco_scores: Dict[str, float],          # version_id -> eco_score (0–1, lower = better)
    feasibility_scores: Dict[str, float],  # version_id -> feasibility_score (0–1, higher = better)
    weight_eco: float = 0.5,
    weight_feasibility: float = 0.5,
) -> str:
    """
    Suggest which branch is more promising based on eco and feasibility metrics.

    This does NOT auto-delete the other branch; it simply provides a
    recommendation that human designers can accept, refine, or override.
    """
    a = version_a_id
    b = version_b_id

    # Lower eco_score is "better" ecologically, so convert to a goodness measure
    eco_good_a = 1.0 - eco_scores.get(a, 0.5)
    eco_good_b = 1.0 - eco_scores.get(b, 0.5)

    feas_a = feasibility_scores.get(a, 0.5)
    feas_b = feasibility_scores.get(b, 0.5)

    score_a = weight_eco * eco_good_a + weight_feasibility * feas_a
    score_b = weight_eco * eco_good_b + weight_feasibility * feas_b

    return a if score_a >= score_b else b
```

In a real implementation, geometric merges and CAD-level reconciliation are handled by specialized tools; this workspace logic coordinates branches as computational objects and references CAD assets by URI/hash.

***

**Math Sketch — Branch Preference Scoring**

For each version $v$, assume we have:
- $E_v$ = eco-impact score, normalized to $[0,1]$, where **lower is better**
- $F_v$ = feasibility score, normalized to $[0,1]$, where **higher is better**

Convert ecological impact into a "goodness" signal:

$$G^{eco}_v = 1 - E_v$$

Define a combined preference score:

$$P_v = \alpha G^{eco}_v + \beta F_v \quad \text{with} \quad \alpha,\beta \ge 0,\ \alpha+\beta=1$$

Given two branches $v_a$ and $v_b$, the workspace prefers $v_a$ if:

$$P_{v_a} \ge P_{v_b}$$

In words: choose the branch that jointly minimizes ecological footprint and maximizes feasibility, according to tunable weights. This is a **soft recommendation**, not a command; human designers can still retain versions for cultural, aesthetic, or context-specific reasons the metrics do not capture.
