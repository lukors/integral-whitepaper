#### Module 2 (CDS) — Issue Structuring & Framing

**Purpose**

Convert raw, heterogeneous submissions—proposals, objections, comments, and system signals—into **coherent issue frames** consisting of clusters, themes, sub-issues, and decision parameters that later CDS modules can reason about.

**Inputs**

- An `Issue` with attached `Submission` objects (from **Module 1**)
- Optional configuration parameters for semantic clustering:
  - embedding model selection
  - similarity thresholds
  - maximum cluster count
  - minimum cluster size

**Outputs**

- A `StructuredIssueView` containing:
  - clustered submissions
  - inferred themes
  - scoped sub-issues
- Updated issue lifecycle state:
  - `Issue.status = "structured"`
  - `Issue.last_updated_at` set

**Design Notes**

- **Evidence submissions are intentionally excluded** from semantic clustering.
   Evidence is indexed and contextualized in **Module 3 (Knowledge Integration & Context Engine)** to prevent conflating claims with sources.
- Deduplicated placeholder submissions (inserted by Module 1) are ignored to preserve signal clarity.
- `StructuredIssueView` and `SubmissionCluster` are **transient computational artifacts**, not canonical CDS records. They exist to support downstream reasoning and deliberation.

***

**Helper Types (for structuring)**

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SubmissionCluster:
    id: str
    issue_id: str
    label: str
    submission_ids: List[str]
    centroid_vector: List[float]


@dataclass
class StructuredIssueView:
    issue_id: str
    clusters: List[SubmissionCluster]
    themes: List[str]
    metadata: Dict[str, Any]
```

***

**Core Logic **

```python
from datetime import datetime
from typing import List, Dict, Any


def embed_text(text: str) -> List[float]:
    """
    Convert text into a semantic vector.
    In practice this may call a local embedding model or an external service.
    """
    return some_embedding_model(text)


def is_clusterable_submission(s: Submission) -> bool:
    """
    Determine whether a submission should be clustered.

    Clusterable:
      - proposals
      - objections
      - comments
      - system signals (e.g. FRS alerts)

    Excluded:
      - evidence submissions (handled in Module 3)
      - deduplication placeholders inserted by Module 1
    """
    if s.type not in ["proposal", "objection", "comment", "signal"]:
        return False

    # Ignore deduplication placeholders
    if isinstance(s.metadata, dict) and "deduplicated_of" in s.metadata:
        return False

    if not s.content or not s.content.strip():
        return False

    return True


def cluster_submissions(
    issue: Issue,
    max_clusters: int = 8,
    min_cluster_size: int = 2,
) -> StructuredIssueView:
    """
    Module 2 — Issue Structuring & Framing
    --------------------------------------
    Takes clusterable submissions attached to an Issue, computes embeddings,
    clusters them into thematic groups, and returns a structured issue view.
    """
    now = datetime.utcnow()

    # 1. Collect clusterable submissions
    subs: List[Submission] = [
        s for s in issue.submissions if is_clusterable_submission(s)
    ]
    texts: List[str] = [s.content for s in subs]

    if not texts:
        issue.status = "structured"
        issue.last_updated_at = now
        return StructuredIssueView(
            issue_id=issue.id,
            clusters=[],
            themes=[],
            metadata={
                "note": "no clusterable submissions",
                "clustered_types": ["proposal", "objection", "comment", "signal"],
                "excluded_types": ["evidence"],
            },
        )

    # 2. Compute embeddings
    embeddings: List[List[float]] = [embed_text(t) for t in texts]

    # 3. Run clustering algorithm (e.g. k-means, agglomerative)
    cluster_labels: List[int] = run_clustering_algorithm(
        embeddings,
        max_clusters=max_clusters,
    )

    # 4. Group submissions by cluster
    grouped: Dict[int, List[Submission]] = {}
    for label, sub in zip(cluster_labels, subs):
        grouped.setdefault(label, []).append(sub)

    submission_clusters: List[SubmissionCluster] = []
    themes: List[str] = []

    # 5. Build clusters and infer labels
    for cluster_id, sub_list in grouped.items():
        if len(sub_list) < min_cluster_size:
            label = f"misc_{cluster_id}"
        else:
            label = infer_cluster_label([s.content for s in sub_list])
            themes.append(label)

        centroid = compute_centroid(
            [e for e, lab in zip(embeddings, cluster_labels) if lab == cluster_id]
        )

        submission_clusters.append(
            SubmissionCluster(
                id=generate_id("cluster"),
                issue_id=issue.id,
                label=label,
                submission_ids=[s.id for s in sub_list],
                centroid_vector=centroid,
            )
        )

    issue.status = "structured"
    issue.last_updated_at = now

    return StructuredIssueView(
        issue_id=issue.id,
        clusters=submission_clusters,
        themes=sorted(list(set(themes))),
        metadata={
            "clustering_method": "kmeans",
            "num_clusters": len(submission_clusters),
            "clustered_types": ["proposal", "objection", "comment", "signal"],
            "excluded_types": ["evidence"],
            "max_clusters": max_clusters,
            "min_cluster_size": min_cluster_size,
        },
    )
```

***

**Math Sketch — Clustering and Similarity**

Let there be $N$ clusterable submissions $\{s_1, s_2, \dots, s_N\}$ with semantic embeddings $e(s_i) \in \mathbb{R}^d$.

The goal is to partition them into $K$ clusters $C_1, \dots, C_K$ (with $K \leq \text{max clusters}$) such that submissions within each cluster are semantically similar.

A standard objective (e.g. *k-means*) is:

$$\min_{C_1,\dots,C_K} \sum_{k=1}^{K} \sum_{s_i \in C_k} \left\| e(s_i) - \mu_k \right\|^2$$

where the centroid of cluster $C_k$ is:

$$\mu_k = \frac{1}{\lvert C_k \rvert} \sum_{s_i \in C_k} e(s_i)$$

Cluster similarity can be assessed via cosine similarity of centroids:

$$\text{sim}(C_a, C_b) = \frac{\mu_a \cdot \mu_b}{\|\mu_a\|\,\|\mu_b\|}$$

For **theme extraction**, a simple heuristic is to:
- extract top-$n$ key phrases from all texts in $C_k$, or
- choose a label that maximizes semantic coherence within the cluster.

The specific clustering algorithm and labeling method are implementation choices. What matters is that **Module 2 transforms a flat list of submissions into a structured, navigable representation of the decision space**—a prerequisite for contextual grounding, constraint checking, and deliberation in later CDS modules.
