#### Module 1 (FRS) — Signal Intake & Semantic Integration

**Purpose**
Ingest, normalize, timestamp, and contextualize structured signals from across Integral—producing coherent **SignalPackets** that represent system state and can be reliably used for diagnosis and modeling.

**Inputs**

Module 1 accepts **interpretable, structured signals** (not raw sensor noise), primarily from:

- **COS** (production summaries, bottlenecks, QA traces, materials ledgers, distribution metrics)
- **OAD** (design valuation profiles, lifecycle models, certification updates, repository reuse metrics)
- **ITC** (valuation drift outputs, scarcity indices, decay distribution statistics, ethics flags)
- **CDS** (policy snapshots, participation/governance load indicators, decision metadata)
- **Ecological monitoring** (water/forest/energy/climate indicators and thresholds)
- **Federated exchanges** (cross-node stress signatures, best practices, model templates)

**Outputs**

- **SignalEnvelope** objects (validated + normalized incoming signals)
- **SignalPacket** objects (time-aligned bundles of envelopes over a window)
- Integrity metadata (quality scores, schema versions, hash chain)
- A minimal routing index (domains/sources/tags present in the packet)

***

**Core Logic (Pseudocode)**

```python
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


# ----------------------------
# Helpers: ID + hashing
# ----------------------------

def generate_id(prefix: str = "frs") -> str:
    return f"{prefix}_{hashlib.sha256(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:12]}"


def stable_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_hash(payload: Dict[str, Any], prev_hash: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update(stable_json(payload).encode("utf-8"))
    if prev_hash:
        h.update(prev_hash.encode("utf-8"))
    return h.hexdigest()


# ----------------------------
# Validation / normalization
# ----------------------------

ALLOWED_SOURCES = {"COS", "OAD", "ITC", "CDS", "ECO", "FED"}

def validate_envelope(envelope: SignalEnvelope) -> None:
    """
    Hard validation: reject malformed or unauthorized envelopes.
    """
    assert envelope.source in ALLOWED_SOURCES, "unknown signal source"
    assert envelope.node_id, "missing node_id"
    assert envelope.created_at is not None, "missing created_at"
    # Minimal sanity checks
    for m in envelope.metrics:
        assert m.name, "metric missing name"
        # allow any unit; value must be numeric
        assert isinstance(m.value, (int, float)), "metric value must be numeric"
        # quality must remain bounded
        assert 0.0 <= m.quality <= 1.0, "metric quality must be in [0,1]"


def normalize_metric_units(envelope: SignalEnvelope, unit_map: Dict[str, str]) -> SignalEnvelope:
    """
    Optional unit normalization pass (e.g. kWh->MJ, lbs->kg),
    controlled by CDS/OAD/FRS schema conventions.
    """
    for m in envelope.metrics:
        # If a mapping exists for metric name + unit, normalize.
        key = f"{m.name}:{m.unit}"
        if key in unit_map:
            target_unit, factor = unit_map[key].split("|")
            factor = float(factor)
            m.value = float(m.value) * factor
            m.unit = target_unit
            m.metadata["normalized_from"] = key
    return envelope


def compute_envelope_quality(envelope: SignalEnvelope) -> float:
    """
    Aggregate data quality as mean(metric.quality), penalized for emptiness.
    """
    if not envelope.metrics:
        return 0.5
    q = sum(m.quality for m in envelope.metrics) / len(envelope.metrics)
    # Penalize if envelope lacks semantic tags (harder to route/interpret)
    if not envelope.tags:
        q *= 0.9
    return max(0.0, min(1.0, q))


# ----------------------------
# Intake: produce tamper-evident envelopes
# ----------------------------

def ingest_signal(
    envelope: SignalEnvelope,
    prev_hash: Optional[str] = None,
    unit_map: Optional[Dict[str, str]] = None,
) -> SignalEnvelope:
    """
    FRS-1 Intake: validate, (optionally) normalize units, compute hash link.
    """
    validate_envelope(envelope)
    if unit_map:
        envelope = normalize_metric_units(envelope, unit_map)

    payload = {
        "id": envelope.id,
        "source": envelope.source,
        "domain": envelope.domain,
        "node_id": envelope.node_id,
        "federation_id": envelope.federation_id,
        "created_at": envelope.created_at.isoformat(),
        "observed_at": envelope.observed_at.isoformat() if envelope.observed_at else None,
        "tags": [(t.key, t.value, t.weight) for t in envelope.tags],
        "metrics": [(m.name, float(m.value), m.unit, float(m.quality)) for m in envelope.metrics],
        "schema_version": envelope.schema_version,
        "upstream_ref_ids": envelope.upstream_ref_ids,
        "notes": envelope.notes,
    }

    envelope.prev_hash = prev_hash
    envelope.entry_hash = compute_hash(payload, prev_hash)
    return envelope


# ----------------------------
# Packetization: time-align envelopes into SignalPackets
# ----------------------------

def build_signal_packet(
    node_id: str,
    time_window_start: datetime,
    time_window_end: datetime,
    envelopes: List[SignalEnvelope],
    prev_packet_hash: Optional[str] = None,
) -> SignalPacket:
    """
    Bundle envelopes into a time window, compute packet quality, and hash-chain the packet.
    """
    # Filter envelopes by node_id and time window
    in_window: List[SignalEnvelope] = []
    for e in envelopes:
        if e.node_id != node_id:
            continue
        t = e.observed_at or e.created_at
        if time_window_start <= t < time_window_end:
            in_window.append(e)

    # Compute packet metadata
    domains_present = sorted(list({e.domain for e in in_window}))
    sources_present = sorted(list({e.source for e in in_window}))

    # Packet quality: mean envelope quality, penalize missing diversity
    if in_window:
        env_q = [compute_envelope_quality(e) for e in in_window]
        quality_score = sum(env_q) / len(env_q)
    else:
        quality_score = 0.5

    # Penalize if only one source dominates (low redundancy)
    if len(sources_present) <= 1:
        quality_score *= 0.9

    packet = SignalPacket(
        id=generate_id("packet"),
        node_id=node_id,
        time_window_start=time_window_start,
        time_window_end=time_window_end,
        envelopes=in_window,
        domains_present=domains_present,
        sources_present=sources_present,
        quality_score=max(0.0, min(1.0, quality_score)),
        packet_version="v1",
        prev_hash=prev_packet_hash,
        packet_hash=None,
    )

    # Hash the packet
    packet_payload = {
        "id": packet.id,
        "node_id": packet.node_id,
        "time_window_start": packet.time_window_start.isoformat(),
        "time_window_end": packet.time_window_end.isoformat(),
        "envelope_hashes": [e.entry_hash for e in packet.envelopes],
        "domains_present": packet.domains_present,
        "sources_present": packet.sources_present,
        "quality_score": packet.quality_score,
        "packet_version": packet.packet_version,
    }
    packet.packet_hash = compute_hash(packet_payload, prev_packet_hash)
    return packet
```

***

**Running Example (Sailboat): Ingest → Packetize**

*Illustrative Signal Flow (Non-Normative Example)*

The following example illustrates how **already structured, upstream-generated signals** are ingested, normalized, and packetized by **FRS-1**. It introduces **no new logic, rules, or authority** beyond the formal specification above, and should be read strictly as an **informative instantiation of the defined data structures**—not as a procedural requirement, execution model, or prescriptive workflow.

```python
# Example signal envelopes arriving from multiple systems for the sailboat context

now = datetime.utcnow()

e1 = SignalEnvelope(
    id=generate_id("env"),
    source="COS",
    domain="materials",
    node_id="node_coastal_A",
    federation_id="coast_region_1",
    created_at=now,
    observed_at=now,
    tags=[SemanticTag("good_id", "sailboat_shared_v1"),
          SemanticTag("material_id", "timber_marine_grade")],
    metrics=[
        Metric("timber_consumed_kg_week", 180.0, "kg", quality=0.95),
        Metric("scrap_rate_pct", 6.5, "%", quality=0.9),
    ],
    notes="Weekly materials summary from COS ledger aggregation."
)

e2 = SignalEnvelope(
    id=generate_id("env"),
    source="ECO",
    domain="ecology",
    node_id="node_coastal_A",
    federation_id="coast_region_1",
    created_at=now,
    observed_at=now,
    tags=[SemanticTag("ecosystem", "coastal_forest_zone_3")],
    metrics=[
        Metric("timber_regeneration_kg_week", 160.0, "kg", quality=0.8),
        Metric("humidity_pct", 82.0, "%", quality=0.9),
        Metric("salinity_index", 0.74, "index", quality=0.85),
    ],
    notes="Ecological monitoring snapshot."
)

# Intake with hash-chaining
env1 = ingest_signal(e1, prev_hash=None)
env2 = ingest_signal(e2, prev_hash=env1.entry_hash)

# Build a weekly packet
week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
week_end = week_start.replace(day=week_start.day + 7)  # illustrative only

packet = build_signal_packet(
    node_id="node_coastal_A",
    time_window_start=week_start,
    time_window_end=week_end,
    envelopes=[env1, env2],
    prev_packet_hash=None,
)

# At this point, Module 2 receives `packet` as its input substrate.
```

***

**Math Sketches**

**1. Packet Quality Score**

Let a packet contain envelopes $e_1, \dots, e_n$.
Each envelope has metric-level qualities $q_{i1}, \dots, q_{ik_i} \in [0,1]$.

Define envelope quality:

$$Q(e_i) = \frac{1}{k_i}\sum_{j=1}^{k_i} q_{ij} \cdot \pi_i$$

where $\pi_i \in (0,1]$ is an optional penalty (e.g., missing tags or single-source weakness).

Packet quality:

$$Q(\text{packet}) = \frac{1}{n}\sum_{i=1}^{n} Q(e_i)$$

Optionally penalize if source diversity is low.

**2. Tamper-Evident Hash Chain (Envelope or Packet)**

For entry payload $P_i$ and previous hash $H_{i-1}$:

$$H_i = \text{SHA256}\big(\text{serialize}(P_i)\ \Vert\ H_{i-1}\big)$$

Changing any past payload breaks all downstream hashes, enabling auditability without tokenization.

***

**Plain-Language Summary**

FRS Module 1 ensures that **nothing enters the system as rumor, assumption, or fragmented data**:
- every operational signal,
- every ecological indicator,
- every valuation shift,
- every governance load marker,

is **normalized, timestamped, contextualized, and preserved** before interpretation.

This gives Integral a shared, auditable picture of reality—so diagnosis, modeling, and democratic decisions are grounded in **what is actually happening**, not in guesses, prices, or authority narratives.
