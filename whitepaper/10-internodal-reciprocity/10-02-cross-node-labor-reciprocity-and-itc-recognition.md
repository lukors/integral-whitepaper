## 10.2 Cross-Node Labor Reciprocity and ITC Recognition

Cross-node labor reciprocity is the most structurally demanding form of internodal cooperation in Integral. Unlike information or design sharing, labor contribution is **rivalrous, time-bounded, and context-dependent**. Individuals expend effort in specific places, under specific conditions, producing outcomes that cannot be duplicated elsewhere. Recognizing such contributions across autonomous nodes—without converting them into a universal currency—requires careful separation between **attestation**, **recognition**, and **access**.

Integral resolves this by treating labor mobility not as exchange, but as **recognized contribution events** that are interpreted locally under shared protocol constraints.

***

**10.2.1 Core Principle: Recognition Without Conversion**

When an individual contributes labor in a node other than their home node, nothing is "paid" and no transferable credit is issued. Instead:

1. The **host node** attests that a contribution occurred, recording objective metadata about the event.
2. The contribution is expressed as a **Contribution Receipt**, not a spendable token.
3. Other nodes may **recognize** that contribution within their own ITC systems, using locally defined weighting parameters constrained by shared equivalence rules.

What moves across nodes is therefore **information about contribution**, not value itself. There is no exchange rate, no fungible unit, and no accumulation pathway.

***

**10.2.2 Contribution Receipt (CR): The Transfer Object**

A **Contribution Receipt (CR)** is the canonical object representing cross-node labor.

Each CR includes:

- contributor identifier (pseudonymous if required),
- host node identifier,
- contribution duration,
- contribution type (skill class, task category),
- context modifiers (risk, hardship, scarcity),
- quality or completion indicators,
- associated design or project references,
- timestamp and duration,
- cryptographic signature of the host node.

Formally, a receipt $c$ is a structured metadata bundle:

$$c = \{ t, h, \tau, \kappa, \rho, \sigma, q, d, \text{sig}_h \}$$

Where:

- $t$ = contributor,
- $h$ = host node,
- $\tau$ = time expended,
- $\kappa$ = contribution category,
- $\rho$ = risk/hardship indicators,
- $\sigma$ = scarcity context,
- $q$ = quality assessment,
- $d$ = design/project reference,
- $\text{sig}_h$ = host attestation.

The CR does **not** contain a numeric value. It is a verifiable statement of fact.

***

**10.2.3 Local ITC Valuation Functions**

Each node maintains its own **ITC valuation function**, reflecting local priorities, constraints, and cultural norms. Given a contribution receipt $c$, node $i$ computes a local recognition value:

$$V_i(c) = \tau \cdot w_i(\kappa) \cdot m_i(\sigma) \cdot r_i(\rho) \cdot q_i(q)$$

Where:

- $w_i(\kappa)$ = local weight for contribution category,
- $m_i(\sigma)$ = scarcity multiplier,
- $r_i(\rho)$ = risk or hardship multiplier,
- $q_i(q)$ = quality adjustment.

This computation occurs **locally** and produces **non-transferable ITC recognition** within node $i$'s system.

***

**10.2.4 Equivalence Bands: Preventing Arbitrage**

To prevent strategic migration or valuation arbitrage, Integral uses **equivalence bands** rather than conversion rates.

For each pair of nodes $(i, j)$, and for each contribution category $\kappa$, a recognition band is defined:

$$B_{ij}(\kappa) = [L_{ij}(\kappa), U_{ij}(\kappa)]$$

When node $j$ recognizes a contribution attested by node $i$, the recognized value is bounded:

$$V_j^{\text{recognized}}(c) = \mathrm{clamp}\big(V_j(c), L_{ij}(\kappa), U_{ij}(\kappa)\big)$$

Bands are:

- symmetric or asymmetric as appropriate,
- category-specific,
- time-smoothed to avoid rapid oscillation,
- derived from historical averages and protocol negotiation.

They ensure **comparability without unification**.

***

**10.2.5 Decay, Non-Transferability, and Access**

Recognized ITC values:

- **decay over time** without continued contribution,
- **cannot be transferred** between individuals,
- **cannot be aggregated into power**, status, or governance rights,
- confer **access**, not ownership.

Access rights derived from ITCs remain bounded by:

- node-level capacity constraints,
- ecological limits,
- fairness rules defined locally.

Cross-node recognition does not override local access ceilings.

***

**10.2.6 Mobility Without Markets**

This architecture enables:

- skilled contributors to assist where needed,
- nodes to benefit from distributed expertise,
- crisis response without wage bidding,
- cultural and technical exchange without labor commodification.

At no point does labor become a tradable good. There is no market for hours, no salary competition, and no incentive to chase "high-value" nodes. Mobility follows **need, interest, and viability**, not price gradients.

***

**10.2.7 Illustrative Pseudo-Code**
```python
def recognize_contribution(receipt, local_profile, band):
    base = (
        receipt.hours
        * local_profile.weight[receipt.category]
        * scarcity_multiplier(receipt.scarcity)
        * risk_multiplier(receipt.risk)
        * quality_multiplier(receipt.quality)
    )
    return clamp(base, band.min, band.max)
```

This function never produces a transferable unit—only a bounded recognition event within the local ITC ledger.

***

**10.2.8 Significance**

Cross-node labor reciprocity in Integral demonstrates that **mobility, specialization, and mutual aid** can exist without labor markets or wages. By separating attestation from recognition, and recognition from access, the system preserves autonomy while enabling cooperation at scale.

The next section extends this logic to **material and capacity reciprocity**, where constrained optimization replaces exchange as the organizing principle.

***

**10.2.9 Illustrative Example: Cross-Node Labor Reciprocity in Practice**

Consider an individual—call her **Alex**—who is a member of **Node A**, a mid-sized manufacturing and repair community. Alex maintains her normal access to housing, food, tools, and materials through Node A's ITC system, based on her ongoing contributions there.

**Step 1: Discovery of Need (No Scope Expansion)**

Through an open, network-wide request interface, Alex learns that **Node B**, located on another continent, is experiencing a temporary labor shortfall in the production of **open-source 3-D printing machines**. The request specifies:

- the design reference (OAD hash),
- required skill class,
- estimated time window,
- and context modifiers (time pressure, tooling availability).

This request does **not** trigger a coordination envelope. It is routine internodal reciprocity, not scope expansion.

**Step 2: Voluntary Labor Mobility**

Alex decides to travel to Node B and contribute directly. There is no contract, no wage negotiation, and no exchange of promises. Node B simply commits to **attesting** any contribution Alex makes.

**Step 3: Contribution and Attestation at Node B**

Alex works **50 hours** assisting with assembly, calibration, and testing of the machines. During this time:

- Node B records the contribution internally (task type, duration, quality, context).
- Alex gains experiential knowledge and access to design improvements through OAD.
- No "payment" is issued.

At the end of the work period, Node B generates a **Contribution Receipt (CR)**, cryptographically signed, stating in effect:

> *"Alex contributed 50 hours of skilled fabrication labor to the production of 3-D printers under design X, meeting quality threshold Y, under normal risk conditions."*

This receipt contains **metadata only**—no numeric value, no spendable token.

**Step 4: Return to Node A**

Alex returns home to Node A. She resumes normal life and continues contributing locally over time.

Alex does **not** "transfer ITCs" from Node B to Node A. Instead, Node A **recognizes** the contribution attested by Node B.

**Step 5: Recognition Under Node A's ITC System**

Node A receives the Contribution Receipt and applies its **local ITC recognition function**.

Node A evaluates the receipt using its own parameters:

- how it weights fabrication labor,
- how it treats off-node contributions,
- what equivalence band applies between Node A and Node B.

Formally (simplified):

$$V_A(c) = \mathrm{clamp}\Big(50 \times w_A(\text{fabrication}) \times q_A(\text{quality}),\; B^-_{BA},\; B^+_{BA}\Big)$$

The result is a **recognized ITC credit within Node A's ledger**. Nothing is converted. Nothing is exchanged. No global balance exists.

**Step 6: Continued Access at Node A**

Alex now continues accessing materials, tools, and services at Node A—including materials needed for her own projects—without interruption.

Importantly:

- Node A does not care *where* the contribution occurred.
- Node B does not lose anything by having attested it.
- No one "owes" anyone else.

What matters is that Alex contributed meaningfully to the network, and that contribution is **legible, bounded, and recognized**.

**What Did Not Happen**

This example is often misunderstood, so it's worth stating explicitly what did **not** occur:

- Alex did not earn money.
- Alex did not receive a transferable credit.
- Node B did not pay Node A.
- Node A did not reimburse Node B.
- No exchange rate was applied.
- No market price emerged.
- No authority approved the transfer.

Only **recognized contribution** moved across nodes.

**Why This Works**

From the system's perspective:

- **Attestation** is local and factual.
- **Recognition** is local and contextual.
- **Access** remains bounded by local capacity and constraints.
- **Mobility** is enabled without commodifying labor.

From Alex's perspective:

- She helps where help is needed.
- She gains experience and knowledge.
- Her contribution continues to support her life at home.
- She never enters a labor market.

This is internodal labor reciprocity **without exchange**, made possible by separating contribution from value, value from access, and access from power.

***

**Good-Faith Contribution, Quality, and Dispute Handling**

Internodal labor reciprocity in Integral does not assume perfect behavior or universal competence. As with any real system involving human effort, contributions may fall short of expectations, be incomplete, or—more rarely—be claimed in bad faith. Integral addresses this not through trust alone, but through **localized attestation, evidentiary standards, and protocol-bounded judgment**.

**1. Attestation Is Issued by the Host Node, Not the Contributor**

An individual does not self-declare their contribution. **All cross-node labor recognition begins with host-node attestation**.

A Contribution Receipt is issued only if the host node's COS/CDS processes confirm that:

- the contributor actually participated,
- the claimed duration is accurate,
- the contribution met baseline expectations of good faith.

If work is abandoned, obstructive, negligent, or misrepresented, the host node simply **does not issue a receipt**, or issues a receipt with downgraded metadata (e.g., partial completion, training-level quality, remediation required).

There is no global authority involved—just the node where the work occurred.

**2. Quality and Completion Are Encoded, Not Assumed**

Contribution Receipts include **qualitative and contextual metadata**, not just hours. This allows recognition to be proportional rather than binary.

Examples:

- *completed as specified*
- *assisted under supervision*
- *training contribution*
- *partial completion*
- *rework required*
- *did not meet quality threshold*

This means hours alone never determine recognition — quality, difficulty, and outcome matter, and inflated claims cannot be smuggled through as time logs. Nodes downstream see the full context of what occurred.

**3. Recognition Is Always Local and Bounded**

Even when a Contribution Receipt is issued, **recognition remains local**. The receiving node applies its own ITC valuation rules, weights quality indicators, and clamps recognition within equivalence bands.

If a contributor consistently produces marginal or problematic outcomes elsewhere, this naturally reflects in **lower recognized value**, without any blacklist or global sanction. No node is required to "believe" another node's attestations beyond protocol bounds.

**4. Bad Faith Does Not Cascade into Punishment**

Integral explicitly avoids punitive escalation. If someone acts in bad faith:

- they receive no receipt, or a low-quality one,
- recognition elsewhere is minimal or zero,
- opportunities naturally diminish.

There is **no global exclusion**, no credit confiscation, no reputation tribunal. Bad actors are constrained by **loss of reciprocity**, not punishment.

**5. Dispute Resolution Is Local and Scoped**

If a contributor disputes a host node's assessment:

- the issue remains between the contributor and the host node,
- resolved through the host's CDS or mediation process,
- optionally documented as a learning artifact.

Disputes do **not** propagate across the network unless they materially affect others (at which point Section 9's scope logic applies).

**6. Why This Is Sufficient (and Safer Than Markets)**

Markets solve mistrust with contracts, litigation, wage withholding, surveillance, and exclusion. Integral solves mistrust with:

- **attestation at the point of action**,
- **evidence-based recognition**,
- **bounded interoperability**,
- **and natural loss of access to reciprocity**.

There is no incentive to inflate hours, because contributors cannot self-issue value, recognition is contextual and capped, and repeated low-quality work yields diminishing returns. Good faith is rewarded structurally; bad faith is filtered structurally.

**7. Summary Principle**

> *Integral does not assume trust—it constrains mistrust. Contribution is attested locally, recognized contextually, bounded globally, and never converted into power.*

This clarification closes a major conceptual loophole without introducing policing, moral scoring, or centralized enforcement.
