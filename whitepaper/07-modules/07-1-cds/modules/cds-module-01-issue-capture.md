#### Module 1 (CDS) — Issue Capture & Signal Intake

**Purpose:**
Collect all proposals, concerns, objections, evidence, and relevant system signals in a **clean, authenticated** format.

**Inputs**

- Raw user input (forms, comments, uploads)
- Participant identities (for authentication)
- Structured signals from other systems (e.g., FRS alerts, ITC adjustment requests, COS capacity flags)

**Outputs**

- An `Issue` with attached, authenticated `Submission` objects ready for structuring (Module 2)

**Core Logic (pseudo-code):**

```python
from datetime import datetime
from typing import Dict, Optional

def authenticate_actor(actor_id: str, actor_type: str) -> bool:
    """
    Identity/authentication check for submissions.

    actor_type:
      - "human"  -> verify DID/credential/session
      - "system" -> verify service identity, signing keys, and allowlist
                  (e.g. FRS, ITC, COS)
    """
    # Placeholder: always passes
    return True


def normalize_actor(
    participant: Optional[Participant],
    system_actor_id: Optional[str],
) -> tuple[str, str]:
    """
    Return (actor_id, actor_type) for either human participants or system sources.
    """
    if participant is not None:
        return participant.id, "human"
    assert system_actor_id is not None, "must provide participant or system_actor_id"
    return system_actor_id, "system"


def intake_submission(
    issue: Issue,
    content: str,
    sub_type: SubmissionType,
    metadata: Dict,
    participant: Optional[Participant] = None,
    system_actor_id: Optional[str] = None,   # e.g. "FRS", "ITC", "COS"
) -> Issue:
    """
    Module 1 — Issue Capture & Signal Intake
    ----------------------------------------
    Adds a submission into the CDS intake stage with authentication,
    deduplication, and structured storage.

    sub_type can be:
      - "proposal"
      - "objection"
      - "evidence"
      - "comment"
      - "signal" (e.g. FRS alert, ITC warning)

    Notes:
      - Human and system submissions are both valid.
      - This module does not evaluate merit; it ensures integrity and traceability.
    """

    actor_id, actor_type = normalize_actor(participant, system_actor_id)

    # Reject input unless identity (human or system) is confirmed
    assert authenticate_actor(actor_id, actor_type), "unauthenticated input"

    submission = Submission(
        id=generate_id("sub"),
        author_id=actor_id,
        issue_id=issue.id,
        type=sub_type,
        content=content,
        created_at=datetime.utcnow(),
        metadata={
            **metadata,
            "actor_type": actor_type,    # "human" | "system"
        },
    )

    # Prevent spam and repeated entries:
    # If near-duplicate, we do NOT store a second full submission by default.
    # Instead, we can increment a counter and store an evidence pointer.
    dup_of = find_near_duplicate(issue.submissions, submission)  # returns submission_id or None

    if dup_of is None:
        issue.submissions.append(submission)
    else:
        # Record deduplication transparently in metadata (keeps auditability)
        # without bloating downstream clustering.
        issue.submissions.append(
            Submission(
                id=generate_id("sub"),
                author_id=actor_id,
                issue_id=issue.id,
                type="comment",  # treated as a linked confirmation rather than a new argument
                content="(deduplicated submission reference)",
                created_at=submission.created_at,
                metadata={
                    "deduplicated_of": dup_of,
                    "original_type": sub_type,
                    "original_content_hash": hash_text(content),
                    "actor_type": actor_type,
                },
            )
        )

    # Maintain issue state + timestamps
    issue.status = "intake"
    issue.last_updated_at = datetime.utcnow()

    return issue

```
**Duplicate Detection — Math Sketch**

To avoid manufactured consensus and redundancy, near-duplicate submissions can be detected using cosine similarity over text embeddings.

Let $e(s)$ be the embedding of submission text $s$.

For a new submission $s_{\text{new}}$ and existing submissions $\{s_i\}$, define:

$$\text{sim}(s_{\text{new}}, s_i) = \frac{e(s_{\text{new}}) \cdot e(s_i)}{\|e(s_{\text{new}})\| \, \|e(s_i)\|}$$

If:

$$\max_i \text{sim}(s_{\text{new}}, s_i) > \tau_{\text{dup}}$$

for some chosen threshold $\tau_{\text{dup}} \in (0, 1)$, then $s_{\text{new}}$ is marked as a near-duplicate and can be merged, collapsed, or flagged rather than added as a distinct submission.

This keeps intake scalable and prevents repetition from overwhelming the later modules.
