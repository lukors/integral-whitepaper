#### Module 7 (CDS) — Decision Recording, Versioning & Accountability

**Purpose**

Module 7 creates a **tamper-evident historical record** of every stage of the CDS process. It ensures that **all governance activity is transparent, auditable, reproducible, and immune to silent revision**.

It records:

- all submissions (human and system)
- structured issue views
- scenario generation and mapping
- contextual and modeling outputs
- constraint reports
- deliberation states
- consensus results
- high-bandwidth human outcomes (Module 9)
- final decisions
- post-decision amendments and overrides (Module 10)

Module 7 is the **institutional memory** of CDS. Without it, CDS would be opaque, manipulable, and epistemically fragile.

It provides:

- verifiable version histories
- hash-linked append-only logs (Merkle/Git-style)
- public dashboards for participants
- reproducibility of every past decision
- the foundation for federated audit and trust

**Inputs**

Module 7 may receive **any artifact produced by CDS Modules 1–10**, including:

- `Issue`
- `Submission`
- `StructuredIssueView`
- `ContextModel`
- `ConstraintReport`
- `DeliberationState`
- `ConsensusResult`
- `Module9Outcome`
- `Decision`
- `ReviewOutcome`
- Metadata (timestamps, participant IDs, rationale, scenario hashes)

**Outputs**

- Append-only `LogEntry` records
- Versioned snapshots of issue state
- Publicly accessible decision history summaries
- Cryptographic attestations (hashes)
- Audit trails usable by:
  - participants
  - node-level oversight
  - inter-node federation review

***

**Helper Type — LogEntry (canonical)**

```python
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime

@dataclass
class LogEntry:
    id: str
    issue_id: str
    stage: str                     # e.g. "intake", "structured", "context_ready",
                                   # "constrained", "deliberation",
                                   # "consensus_check", "decided",
                                   # "amended", "revoked"
    timestamp: datetime
    payload: Dict[str, Any]        # serialized CDS artifact
    prev_hash: str                 # hash of previous log entry
    entry_hash: str                # cryptographic integrity hash
```

***

**Core Logic**

```python
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Any


def compute_hash(payload: Dict[str, Any], prev_hash: str) -> str:
    """
    Compute a cryptographic hash of:
      - the payload (canonical JSON)
      - the previous hash (hash chain)
    """
    serialized = json.dumps(payload, sort_keys=True, default=str)
    h = hashlib.sha256()
    h.update(serialized.encode("utf-8"))
    h.update(prev_hash.encode("utf-8"))
    return h.hexdigest()


def append_log(
    issue_id: str,
    stage: str,
    payload: Dict[str, Any],
    log_chain: List[LogEntry],
) -> LogEntry:
    """
    Module 7 — Decision Recording, Versioning & Accountability
    -----------------------------------------------------------
    Append a new tamper-evident log entry to the CDS history.
    """
    prev_hash = log_chain[-1].entry_hash if log_chain else "GENESIS"
    now = datetime.utcnow()

    entry = LogEntry(
        id=generate_id("log"),
        issue_id=issue_id,
        stage=stage,
        timestamp=now,
        payload=payload,
        prev_hash=prev_hash,
        entry_hash=compute_hash(payload, prev_hash),
    )

    log_chain.append(entry)
    return entry
```

***

**Public Dashboard View**

```python
def summarize_issue_history(
    log_chain: List[LogEntry],
    issue_id: str
) -> Dict[str, Any]:
    """
    Generate a lightweight, human-readable audit trail
    for a specific issue.
    """
    history = []
    for entry in log_chain:
        if entry.issue_id == issue_id:
            history.append({
                "stage": entry.stage,
                "timestamp": entry.timestamp.isoformat(),
                "hash": entry.entry_hash,
                "prev_hash": entry.prev_hash,
            })

    return {
        "issue_id": issue_id,
        "history": history,
        "integrity_valid": validate_hash_chain(log_chain, issue_id),
    }
```

***

**Chain Integrity Validation**

```python

def validate_hash_chain(
    log_chain: List[LogEntry],
    issue_id: str
) -> bool:
    """
    Verify integrity of the hash chain for a given issue.
    """
    previous = "GENESIS"

    for entry in log_chain:
        if entry.issue_id != issue_id:
            continue

        recomputed = compute_hash(entry.payload, previous)
        if recomputed != entry.entry_hash:
            return False

        previous = entry.entry_hash

    return True
```

***

**Math Sketch — Merkle-Style Attestation**

Each log entry hash is computed as:

$$H_i = \mathrm{SHA256}\big(\mathrm{serialize}(P_i) \;\Vert\; H_{i-1}\big)$$

Where:
- $P_i$ is the payload of entry $i$
- $H_{i-1}$ is the previous entry's hash

This guarantees:
- any modification breaks the chain
- deletions are detectable
- reordering is impossible
- the full decision lineage is reproducible

This provides **blockchain-grade integrity without blockchain overhead**.

***

**Semantic Summary**

Module 7 ensures:
- **historical transparency** — every decision step is inspectable
- **tamper-evidence** — no retroactive edits
- **epistemic legitimacy** — all disputes reference the same record
- **federated trust** — nodes can verify one another's governance
- **institutional memory** — learning persists across time

Without Module 7, CDS could drift, obscure rationale, or silently override public consensus. With it, CDS becomes a **verifiable democratic protocol**, not a black-box governance tool.
