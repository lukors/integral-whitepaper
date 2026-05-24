#### Module 4 (ITC) — Labor Forecasting & Need Anticipation

**Purpose**
Align ITC weighting *proposals* with **actual future labor needs**, so the system neither over-rewards unneeded work nor under-recognizes critical tasks. This module forecasts *where* and *when* labor will be needed (by skill tier and sector) and produces bounded recommendations for weighting adjustments and training focus.

**Role in the system**
Modules 1–3 operate at the **event / account** layer (capture → weighting → decay). Module 4 lifts to the **planning layer**, using:

- COS pipelines (task queues, maintenance calendars, throughput constraints),
- OAD roadmaps (designs entering production, redesign cycles),
- FRS signals (seasonal/ecological shocks, stress indicators),
- recent participation patterns (what people are actually doing).

Module 4 does **not compel participation**. It produces *bounded* recommendations that can be:

- applied automatically only within CDS pre-approved tolerance bands, or
- routed to CDS for deliberation when larger changes are implied.

**Inputs**

- `NodeContext` (node state: population, skills, cooperatives, climate, seasonal calendar, etc.)
- `LaborDemandSignal`s from:
  - COS (production queues, maintenance schedules)
  - OAD (upcoming deployments, redesign transitions)
  - FRS (ecological shocks, seasonal stressors, anomaly alerts)
- Historical `LaborEvent` (recent weeks/months)
- CDS policy parameters (forecast horizon bounds, sensitivity caps, max adjustment rates)

**Outputs**

- `LaborDemandForecast` (forecasted demand by skill tier/sector; bottleneck skills)
- A supply estimate by skill tier (derived from recent participation)
- `shortage_index_by_skill` (relative shortage/surplus signals)
- **Recommended weight multipliers** by skill tier (gentle, bounded)
- **Suggested training priorities** (skills/sectors most likely to bottleneck)

These recommendations feed:

- **Module 2** (as candidate context modifiers / policy hints),
- **CDS** (as deliberation inputs for training capacity, workload norms, and bounded parameter updates).

***

**Core Logic **

Core Types (local to this module)

```python
from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple
from datetime import datetime, timedelta
from math import tanh

SkillTier = Literal["low", "medium", "high", "expert"]

@dataclass
class LaborDemandSignal:
    node_id: str
    source: Literal["COS", "OAD", "FRS"]
    skill_tier: SkillTier
    hours_required: float              # for the signal's horizon
    horizon_days: int
    sector: str                        # e.g. "water", "food", "energy"
    confidence: float = 1.0            # 0–1 confidence/priority weight

@dataclass
class LaborForecast:
    node_id: str
    generated_at: datetime
    horizon_days: int
    demand_by_skill: Dict[SkillTier, float]
    supply_by_skill: Dict[SkillTier, float]
    shortage_index_by_skill: Dict[SkillTier, float]   # σ_s = (D_s - S_s) / S_s
    training_priorities: List[str]                     # human-readable targets
    assumptions: Dict
```

**Global-ish containers (illustrative)**

```python
DEMAND_SIGNALS: List[LaborDemandSignal] = []
HISTORICAL_EVENTS: List[LaborEvent] = []   # uses LaborEvent.end_time for time filtering
```

***

1) Aggregate demand (by skill, optionally also by sector)

```python
def aggregate_labor_demand(
    node_id: str,
    horizon_days: int,
    signals: List[LaborDemandSignal],
) -> Dict[SkillTier, float]:
    """
    Aggregate weighted labor demand per skill tier for a unified forecast horizon.
    """
    demand: Dict[SkillTier, float] = {"low": 0.0, "medium": 0.0, "high": 0.0, "expert": 0.0}

    for sig in signals:
        if sig.node_id != node_id:
            continue

        # Scale signals to the requested horizon (bounded so we don't explode small-horizon signals).
        scale = min(horizon_days / max(sig.horizon_days, 1), 2.0)

        demand[sig.skill_tier] += sig.hours_required * sig.confidence * scale

    return demand
```

***

2) Estimate supply (from recent participation)

```python
def estimate_labor_supply_from_history(
    node_id: str,
    horizon_days: int,
    lookback_days: int = 60,
) -> Dict[SkillTier, float]:
    """
    Estimate future labor supply by skill tier by scaling a recent participation window.
    Uses LaborEvent.end_time (not an undefined ev.timestamp).
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=lookback_days)

    hours_by_skill: Dict[SkillTier, float] = {"low": 0.0, "medium": 0.0, "high": 0.0, "expert": 0.0}

    for ev in HISTORICAL_EVENTS:
        if ev.node_id != node_id:
            continue
        if ev.end_time < cutoff:
            continue
        hours_by_skill[ev.skill_tier] += ev.hours

    # Convert observed hours to forecast hours for the horizon
    days_observed = max(lookback_days, 1)
    supply_forecast: Dict[SkillTier, float] = {}
    for tier, total_hours in hours_by_skill.items():
        avg_per_day = total_hours / days_observed
        supply_forecast[tier] = avg_per_day * horizon_days

    return supply_forecast
```

***

3) Compute shortage index σ (demand vs supply)

```python
def compute_shortage_index(
    demand: Dict[SkillTier, float],
    supply: Dict[SkillTier, float],
    eps: float = 1e-6,
) -> Dict[SkillTier, float]:
    """
    σ_s = (D_s - S_s) / S_s
      σ_s > 0 => shortage
      σ_s < 0 => surplus
      σ_s = 0 => balanced
    """
    sigma: Dict[SkillTier, float] = {}
    for tier in demand.keys():
        D = demand[tier]
        S = max(supply.get(tier, 0.0), eps)
        sigma[tier] = (D - S) / S
    return sigma
```

***

4) Recommend bounded weight multipliers (policy hints)

```python
def recommend_weight_multipliers(
    shortage_index: Dict[SkillTier, float],
    max_boost: float = 0.5,   # e.g. up to +50%
    max_cut: float = 0.3,     # e.g. down to -30%
) -> Dict[SkillTier, float]:
    """
    Map σ_s into a smooth multiplier m_s around 1.0.
    Positive σ => increase weight; negative σ => gently decrease.
    """
    multipliers: Dict[SkillTier, float] = {}

    for tier, sigma in shortage_index.items():
        if sigma > 0:
            m = 1.0 + max_boost * tanh(sigma)   # saturates smoothly
            m = min(1.0 + max_boost, m)
        else:
            m = 1.0 + max_cut * tanh(sigma)     # tanh(negative) < 0 => below 1.0
            m = max(1.0 - max_cut, m)

        multipliers[tier] = m

    return multipliers
```

***

5) Training priority suggestion (simple, explainable)

```python
def suggest_training_priorities(
    shortage_index: Dict[SkillTier, float],
    top_k: int = 2,
) -> List[str]:
    """
    Produce a human-readable list of training priorities based on the largest shortages.
    """
    ranked = sorted(shortage_index.items(), key=lambda kv: kv[1], reverse=True)  # biggest σ first
    priorities = []
    for tier, sigma in ranked[:top_k]:
        if sigma > 0:
            priorities.append(f"Expand training / onboarding for {tier}-tier work (shortage σ≈{sigma:.2f}).")
    return priorities
```

***

6) Main forecasting function

```python
def generate_labor_forecast(
    node_ctx,
    horizon_days: int = 30,
    lookback_days: int = 60,
) -> Tuple[LaborForecast, Dict[SkillTier, float]]:
    """
    ITC Module 4 — Labor Forecasting & Need Anticipation
    Produces:
      - a forecast object (demand/supply/shortage + training priorities)
      - recommended multipliers (policy hints to Module 2 / CDS)
    """
    node_id = node_ctx.node_id
    now = datetime.utcnow()

    signals = [s for s in DEMAND_SIGNALS if s.node_id == node_id]

    demand = aggregate_labor_demand(node_id=node_id, horizon_days=horizon_days, signals=signals)
    supply = estimate_labor_supply_from_history(node_id=node_id, horizon_days=horizon_days, lookback_days=lookback_days)

    shortage_index = compute_shortage_index(demand, supply)
    multipliers = recommend_weight_multipliers(shortage_index)

    training_priorities = suggest_training_priorities(shortage_index)

    forecast = LaborForecast(
        node_id=node_id,
        generated_at=now,
        horizon_days=horizon_days,
        demand_by_skill=demand,
        supply_by_skill=supply,
        shortage_index_by_skill=shortage_index,
        training_priorities=training_priorities,
        assumptions={
            "lookback_days": lookback_days,
            "signal_sources": ["COS", "OAD", "FRS"],
            "note": "Forecast informs weighting/training proposals; does not compel participation.",
        },
    )

    return forecast, multipliers
```

***

**Math Sketch — Shortage Index and Weight Adjustment**

For each skill tier $s$:
- $D_s$ = forecasted demand (hours) over horizon $H$
- $S_s$ = forecasted supply (hours) over the same horizon

Define **shortage index**:

$$\sigma_s = \frac{D_s - S_s}{S_s}$$

Map $\sigma_s$ to a bounded multiplier $m_s$ using a smooth saturating function:

If $\sigma_s > 0$ (shortage): $\quad m_s = 1 + B_{\max}\tanh(\sigma_s)$

If $\sigma_s \le 0$ (surplus): $\quad m_s = 1 + C_{\max}\tanh(\sigma_s)$

Then apply to the CDS-defined base weight:

$$w'_s = w^{\text{base}}_s \cdot m_s$$

*Note:* these are **policy hints**. CDS can accept them within pre-approved bounds or deliberate when larger shifts are implied.
