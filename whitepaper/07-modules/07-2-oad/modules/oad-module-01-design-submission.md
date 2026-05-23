#### Module 1 (OAD) — Design Submission & Structured Specification

**Purpose**

Transform raw design ideas into structured, technically complete design specifications that can move through collaborative refinement, ecological assessment, labor decomposition, and simulation.

**Role in the System**

This is the intake gateway for OAD. Nothing enters the design commons as an operative design object until it passes through this module in structured form. Module 1 ensures:

- minimal completeness
- consistent metadata
- clear functional goals
- basic technical coherence

so that later modules (collaborative design, material–ecology analysis, lifecycle modeling, labor-step decomposition, etc.) have something computable to work with.

**Inputs**

- Raw proposal data (forms, uploads, sketches, descriptive text)
- Creator identity (for authentication)
- Initial metadata (sector, node, climate, etc.)

**Outputs**

- A `DesignSpec` object
- An initial `DesignVersion` (e.g., `"v0.1-initial-submission"`) linked to that spec

***

**Core Logic **

```python
from typing import Tuple, Dict, Any
from datetime import datetime


def authenticate_designer(creator_id: str) -> bool:
    """
    Identity/authentication check for design submissions.
    In a real implementation this would verify:
    - decentralized ID / credentials
    - signatures
    - revocation status, etc.
    """
    return True  # placeholder


REQUIRED_FIELDS = [
    "functional_goals",
    "components",
    "cad_files",
    "materials",
    "env_assumptions",
    "performance_criteria",
]


def _is_nonempty(value: Any) -> bool:
    """
    Conservative non-empty check for completeness scoring.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def compute_completeness_score(payload: Dict[str, Any]) -> float:
    """
    Simple completeness heuristic: fraction of required fields
    that are present and non-empty in the submission payload.
    """
    filled = 0
    for field_name in REQUIRED_FIELDS:
        if field_name in payload and _is_nonempty(payload[field_name]):
            filled += 1
    return filled / len(REQUIRED_FIELDS)


def intake_design_submission(
    creator_id: str,
    title: str,
    description: str,
    payload: Dict[str, Any],
    metadata: Dict[str, Any],
    min_completeness: float = 0.7,
) -> Tuple[DesignSpec, DesignVersion]:
    """
    OAD Module 1 — Design Submission & Structured Specification
    -----------------------------------------------------------
    Takes a raw design proposal and converts it into:
      - a DesignSpec (high-level concept)
      - an initial DesignVersion (concrete v0.x instance)
    """

    # 1) Identity check
    assert authenticate_designer(creator_id), "unauthenticated design submission"

    # 2) Completeness check
    completeness = compute_completeness_score(payload)
    if completeness < min_completeness:
        raise ValueError(f"incomplete submission, completeness={completeness:.2f}")

    # 3) Create the high-level specification
    spec = DesignSpec(
        id=generate_id("spec"),
        title=title,
        description=description,
        creator_id=creator_id,
        created_at=datetime.utcnow(),
        functional_goals=payload.get("functional_goals", []),
        components=payload.get("components", []),
        cad_files=payload.get("cad_files", []),
        materials=payload.get("materials", []),
        env_assumptions=payload.get("env_assumptions", {}),
        performance_criteria=payload.get("performance_criteria", {}),
        safety_considerations=payload.get("safety_considerations", []),
        maintenance_expectations=payload.get("maintenance_expectations", {}),
        metadata=metadata,
    )

    # 4) Create the initial version linked to that spec
    version = DesignVersion(
        id=generate_id("version"),
        spec_id=spec.id,
        parent_version_id=None,
        label="v0.1-initial-submission",
        created_at=datetime.utcnow(),
        authors=[creator_id],
        cad_files=spec.cad_files,
        materials=spec.materials,
        parameters=payload.get("parameters", {}),
        change_log="Initial submitted version.",
        status="draft",
        superseded_by_version_id=None,
    )

    return spec, version
```

***

**Math Sketch — Completeness Heuristic**

Let:
- $F$ = set of required fields
- $f_i \in F$ = each required field
- $I(f_i) = 1$ if field $f_i$ is present and non-empty, otherwise $0$

Define completeness score:

$$C_{\text{complete}} = \frac{1}{\lvert F \rvert} \sum_{f_i \in F} I(f_i)$$

A submission is accepted if:

$$C_{\text{complete}} \ge \tau_{\min}$$

where $\tau_{\min}$ is a configurable threshold (e.g., 0.7).

In plain terms: A design enters OAD only when enough key fields are filled to make it processable by later modules.
