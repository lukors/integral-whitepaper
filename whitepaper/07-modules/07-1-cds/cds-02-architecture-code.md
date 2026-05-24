### Formal CDS Specification: Pseudocode + Math Sketches

The preceding subsections described the Collaborative Decision System (CDS) in conceptual and narrative terms: what each module does, how it supports democratic coordination, and how the modules interact to turn raw human input into coherent, constrained, collectively legitimate decisions. To move from description to implementation, this section presents a formal, programmable view of CDS.

What follows is not production code, but implementation-oriented pseudocode and simple mathematics showing how CDS can be represented in software. Each module is expressed as:

- a small set of core data types (issues, submissions, scenarios, votes, objections, decisions, and review artifacts),
- functions that transform these types (intake, clustering, context building, constraint checking, deliberation support, consensus synthesis, recording/versioning, dispatch, and review loops), and
- where appropriate, explicit formulas for key quantities such as similarity scores, constraint checks, consensus gradients, and objection indices.

The goal here is threefold:

1. **Demonstrate feasibility.** Show that the deliberative pipeline described earlier is not vague or magical; it can be encoded in clear data structures and algorithms.
2. **Clarify information flow.** Make explicit how signals move from one module to another (e.g., from submissions → structured issue map → context → constraints → deliberation → consensus → record → dispatch → review).
3. **Provide a bridge for implementers.** Give engineers, data scientists, and system designers a concrete starting point for prototyping CDS within real software stacks (e.g., integrating with tools like Decidim, Loomio, Polis, or custom agent-centric architectures).

Readers who are not interested in the technical details can skim or skip the code while still grasping the high-level intent: CDS is a cybernetic governance engine with clearly defined inputs, outputs, and transformation rules—not an abstract “platform for discussion.” For those building Integral nodes in practice, these sketches provide a baseline blueprint that can be refined, modularized, or replaced with more sophisticated implementations over time.

With that in mind, we begin with a set of shared data types that all CDS modules use. The code below defines the core entities that make democratic deliberation computable:

- an **Issue** is a decision to be resolved
- a **Submission** is any proposal, objection, evidence, comment, or system signal
- a **Scenario** represents one possible solution path
- **Votes** and **Objections** encode gradient preference and principled resistance
- a **Decision** is the synthesized outcome of the deliberation pipeline
- **Participants** have identity, role context, and decision weight

*(Modules 9 and 10 include structured human resolution and post-decision review, respectively; while these cannot be reduced to computation alone, their inputs and outputs are still represented formally and recorded in the same auditable pipeline.)*

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal, Tuple
from datetime import datetime


# ============================================================
# Core CDS enums / literals
# ============================================================

SupportLevel = Literal[
    "strong_support",
    "support",
    "neutral",
    "concern",
    "block",
]

SubmissionType = Literal[
    "proposal",
    "objection",
    "evidence",
    "comment",
    "signal",   # e.g. alerts from FRS, ITC, COS
]

IssueStatus = Literal[
    "intake",          # Module 1 active
    "structured",      # Module 2 complete
    "context_ready",   # Module 3 complete
    "constrained",     # Module 4 complete
    "deliberation",    # Module 5 active
    "consensus_check", # Module 6 active
    "decided",         # decision chosen + recorded
    "dispatched",      # Module 8 executed (dispatch emitted)
    "under_review",    # Module 10 active
    "reopened",        # returned to Module 1/2 due to review outcome
    "archived",        # closed / historical
]

DecisionStatus = Literal[
    "approved",
    "rejected",
    "revise_and_retry",
    "amended",         # Module 10: decision modified
    "revoked",         # Module 10: decision reversed
    "reopened",        # Module 10: sent back into pipeline
]

ConsensusDirective = Literal[
    "approve",
    "revise",
    "escalate_to_module9",
]

ReviewReason = Literal[
    "frs_risk_signal",
    "cos_implementation_failure",
    "itc_equity_drift",
    "constraint_violation",
    "new_evidence",
    "changed_conditions",
    "other",
]

ReviewOutcomeStatus = Literal[
    "reaffirmed",
    "amended",
    "revoked",
    "reopen_deliberation",
]


# ============================================================
# Foundational entities
# ============================================================

@dataclass
class Participant:
    """
    CDS participant with an identity and a decision weight.

    weight is normally 1.0, but may be adjusted by CDS constitutional rules
    (e.g., bounded equalization, protected-category considerations, etc.).
    """
    id: str
    weight: float = 1.0
    roles: List[str] = field(default_factory=list)  # e.g. ["resident", "engineer"]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Submission:
    """
    Any input into CDS: proposal, objection, evidence, comment, or system signal.
    """
    id: str
    author_id: str                 # human participant or system agent ID
    issue_id: str
    type: SubmissionType
    content: str                   # free text or structured JSON-as-string
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)  # tags, links, source system, etc.


@dataclass
class Issue:
    """
    A governance question to be resolved by CDS.
    """
    id: str
    title: str
    description: str
    created_at: datetime
    status: IssueStatus = "intake"
    submissions: List[Submission] = field(default_factory=list)

    # Optional structured metadata for routing/federation:
    tags: Dict[str, str] = field(default_factory=dict)      # e.g. {"sector": "infrastructure", "node": "A"}
    priority: Optional[str] = None                          # e.g. "routine" | "urgent"
    last_updated_at: Optional[datetime] = None


@dataclass
class Scenario:
    """
    A candidate solution path for an Issue.
    """
    id: str
    issue_id: str
    label: str                    # e.g. "Raised walkway", "Alternative route"
    parameters: Dict[str, Any] = field(default_factory=dict)  # inputs used to evaluate/implement
    indicators: Dict[str, float] = field(default_factory=dict) # projected outcomes (filled by modeling)


@dataclass
class Vote:
    """
    Gradient preference signal, not a binary ballot.
    """
    participant_id: str
    issue_id: str
    scenario_id: str
    support: SupportLevel
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Objection:
    """
    A principled objection with severity and scope.
    """
    participant_id: str
    issue_id: str
    scenario_id: str
    severity: float               # 0–1 (how serious is the objection?)
    scope: float                  # 0–1 (how widely does it apply?)
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# CDS Module artifacts (1–10)
# ============================================================

@dataclass
class StructuredIssueView:
    """
    Output of Module 2 (structuring). A transient computational scaffold.
    """
    issue_id: str
    themes: List[str] = field(default_factory=list)
    clusters: List[Dict[str, Any]] = field(default_factory=list)  # can store cluster labels + submission ids
    scope_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextModel:
    """
    Output of Module 3 (knowledge integration). A transient computed context layer.
    """
    issue_id: str
    ecological: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    labor: Dict[str, Any] = field(default_factory=dict)
    historical: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, Any] = field(default_factory=dict)
    social: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintReport:
    """
    Output of Module 4 (constraint checking).
    """
    issue_id: str
    scenario_id: str
    passed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    required_modifications: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliberationState:
    """
    Output of Module 5 (deliberation workspace). Transient but recordable.
    """
    issue_id: str
    active_scenarios: List[Scenario] = field(default_factory=list)
    objections: List[Objection] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """
    Output of Module 6 (weighted consensus).
    """
    issue_id: str
    scenario_id: str
    consensus_score: float
    objection_index: float
    directive: ConsensusDirective            # approve | revise | escalate_to_module9
    required_conditions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """
    Canonical governance output. Must be recorded (Module 7) and dispatched (Module 8).
    """
    id: str
    issue_id: str
    scenario_id: str
    status: DecisionStatus
    consensus_score: float
    objection_index: float
    decided_at: datetime
    rationale_hash: str                    # hash/link to tamper-evident record chain (Module 7)
    supersedes_decision_id: Optional[str] = None  # for amendments/revocations (Module 10)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogEntry:
    """
    Module 7: append-only log entry for transparency/versioning.
    """
    id: str
    issue_id: str
    stage: str                            # e.g. "intake", "structured", "context_ready", "decided", ...
    timestamp: datetime
    payload: Dict[str, Any]
    prev_hash: str
    entry_hash: str


@dataclass
class DispatchPacket:
    """
    Module 8: structured action bundle for OAD/COS/ITC/FRS.
    """
    id: str
    issue_id: str
    scenario_id: str
    created_at: datetime

    tasks: List[Dict[str, Any]] = field(default_factory=list)      # COS tasks
    materials: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)

    oad_flags: Dict[str, Any] = field(default_factory=dict)        # design updates
    itc_adjustments: Dict[str, Any] = field(default_factory=dict)  # weighting/access rules (if relevant)
    frs_monitors: List[str] = field(default_factory=list)          # what to monitor post-implementation

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Module9Outcome:
    """
    Module 9: structured output of high-bandwidth human deliberation.
    This is not computed, but its outputs are formal and auditable.
    """
    issue_id: str
    scenario_id: str
    outcome_summary: str
    modifications: List[str] = field(default_factory=list)      # e.g. amendments to scenario parameters
    unresolved_notes: str = ""
    concluded_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewRequest:
    """
    Module 10: trigger to reassess a past decision.
    """
    id: str
    issue_id: str
    decision_id: str
    reason: ReviewReason
    created_at: datetime
    submitted_by: str                       # "FRS" | "COS" | "ITC" | "member:<id>" | etc.
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewOutcome:
    """
    Module 10: the result of the review loop.
    """
    id: str
    issue_id: str
    decision_id: str
    status: ReviewOutcomeStatus             # reaffirmed | amended | revoked | reopen_deliberation
    new_constraints: Dict[str, Any] = field(default_factory=dict)
    amendments: Dict[str, Any] = field(default_factory=dict)    # scenario/dispatch amendments
    rationale: str = ""
    decided_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

```

***
