#### Putting It Together: CDS Orchestration

Below is a compact orchestration function showing how Modules 1–9 (and 10) operate as a unified pipeline.

```python
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def run_cds_pipeline(
    issue: Issue,
    participants: List[Participant],
    # Inputs from other systems (snapshots)
    frs_data: Dict[str, Any],
    cos_data: Dict[str, Any],
    itc_data: Dict[str, Any],
    oad_data: Dict[str, Any],
    historical_records: List[Dict[str, Any]],
    external_datasets: Dict[str, Any],
    # CDS constitutional / policy rules
    rules: Dict[str, Any],
    # Persistent stores (conceptual)
    log_chain: List[LogEntry],
    # Optional prior decision state (for Module 10)
    prior_decision: Optional[Decision] = None,
    review_request: Optional[ReviewRequest] = None,
) -> Dict[str, Any]:
    """
    End-to-end CDS orchestration across Modules 1–10.

    This driver is intentionally high-level:
      - Modules 1–9 comprise the primary decision metabolism
      - Module 10 is a post-decision supervisory loop

    Notes:
      - CDS remains the normative authority.
      - FRS/COS/ITC/OAD provide signals and constraints; they do not decide.
      - Module 7 records every stage in a tamper-evident chain.
    """

    now = datetime.utcnow()

    # =========================================================
    # MODULE 10 — Review, Revision & Override (post-decision loop)
    # =========================================================
    # If a prior decision exists and a review request is active, process it first.
    # If the outcome is "reopen_deliberation", the issue is reopened into Modules 1–6.
    review_outcome: Optional[ReviewOutcome] = None
    amended_decision: Optional[Decision] = None

    if prior_decision is not None and review_request is not None:
        issue.status = "under_review"
        issue.last_updated_at = now

        review_outcome = evaluate_review_request(
            decision=prior_decision,
            review_request=review_request,
            frs_data=frs_data,
            cos_logs=cos_data,
            itc_data=itc_data,
            constraints=rules.get("constitutional", {}),
        )

        # Record review request + outcome (Module 7)
        append_log(
            issue_id=issue.id,
            stage="under_review",
            payload={
                "review_request": review_request.__dict__,
                "review_outcome": review_outcome.__dict__,
            },
            log_chain=log_chain,
        )

        if review_outcome.status == "reaffirmed":
            # Decision stands; no reopen
            return {
                "status": "reaffirmed",
                "issue_id": issue.id,
                "decision_id": prior_decision.id,
                "review_outcome": review_outcome,
            }

        if review_outcome.status == "revoked":
            # Decision revoked; reopen or terminate based on governance choice
            issue.status = "reopened"
            issue.last_updated_at = now
            append_log(
                issue_id=issue.id,
                stage="reopened",
                payload={"reason": "decision_revoked", "review_outcome": review_outcome.__dict__},
                log_chain=log_chain,
            )
            # Continue into normal pipeline as reopened issue

        if review_outcome.status == "amended":
            # Create amended decision (recorded + dispatched)
            amended_decision = Decision(
                id=generate_id("decision"),
                issue_id=prior_decision.issue_id,
                scenario_id=prior_decision.scenario_id,
                status="amended",
                consensus_score=prior_decision.consensus_score,
                objection_index=prior_decision.objection_index,
                decided_at=now,
                rationale_hash=log_chain[-1].entry_hash if log_chain else "GENESIS",
                supersedes_decision_id=prior_decision.id,
                metadata={
                    "review_outcome": review_outcome.__dict__,
                    "amendments": review_outcome.amendments,
                },
            )

            append_log(
                issue_id=issue.id,
                stage="amended",
                payload={"decision": amended_decision.__dict__},
                log_chain=log_chain,
            )

            # Dispatch amended decision (Module 8)
            # (In practice, scenario parameters would be updated from review_outcome.amendments)
            dispatch = generate_dispatch(
                issue=issue,
                decision=amended_decision,
                consensus=ConsensusResult(
                    issue_id=issue.id,
                    scenario_id=amended_decision.scenario_id,
                    consensus_score=amended_decision.consensus_score,
                    objection_index=amended_decision.objection_index,
                    directive="approve",
                    required_conditions=[],
                    metadata={"reason": "module10_amendment"},
                ),
                scenario=Scenario(id=amended_decision.scenario_id, issue_id=issue.id, label="(amended)", parameters={}, indicators={}),
                constraint_report=ConstraintReport(issue_id=issue.id, scenario_id=amended_decision.scenario_id, passed=True),
                cos_capacity_snapshot=cos_data.get("capacity_snapshot", {}),
            )

            append_log(
                issue_id=issue.id,
                stage="dispatched",
                payload={"dispatch": dispatch.__dict__},
                log_chain=log_chain,
            )

            return {
                "status": "amended_and_dispatched",
                "issue_id": issue.id,
                "decision": amended_decision,
                "dispatch": dispatch,
                "review_outcome": review_outcome,
            }

        if review_outcome.status == "reopen_deliberation":
            issue.status = "reopened"
            issue.last_updated_at = now
            append_log(
                issue_id=issue.id,
                stage="reopened",
                payload={"reason": "review_reopen_deliberation", "review_outcome": review_outcome.__dict__},
                log_chain=log_chain,
            )
            # Continue into normal pipeline as reopened issue

    # =========================================================
    # MODULE 1 — Issue Capture & Signal Intake
    # =========================================================
    # (In practice, submissions arrive continuously; here we assume issue already contains submissions.)
    issue.status = "intake"
    issue.last_updated_at = now
    append_log(
        issue_id=issue.id,
        stage="intake",
        payload={"issue": {"id": issue.id, "title": issue.title, "status": issue.status}},
        log_chain=log_chain,
    )

    # =========================================================
    # MODULE 2 — Issue Structuring & Framing
    # =========================================================
    structured_view = cluster_submissions(issue)
    append_log(
        issue_id=issue.id,
        stage="structured",
        payload={"structured_view": structured_view.__dict__},
        log_chain=log_chain,
    )

    # =========================================================
    # MODULE 3 — Knowledge Integration & Context Engine
    # =========================================================
    context = build_context_model(
        issue=issue,
        structured=structured_view,
        frs_data=frs_data,
        cos_data=cos_data,
        itc_data=itc_data,
        historical_records=historical_records,
        external_datasets=external_datasets,
    )
    append_log(
        issue_id=issue.id,
        stage="context_ready",
        payload={"context": context.__dict__},
        log_chain=log_chain,
    )

    # =========================================================
    # Candidate scenario generation (bridge between M3 and M4)
    # =========================================================
    scenarios: List[Scenario] = generate_candidate_scenarios(issue, structured_view, context, oad_data)
    if not scenarios:
        append_log(
            issue_id=issue.id,
            stage="no_scenarios",
            payload={"note": "No candidate scenarios generated; requires reframing or more input."},
            log_chain=log_chain,
        )
        return {"status": "no_scenarios", "issue_id": issue.id}

    # =========================================================
    # MODULE 4 — Norms & Constraint Checking
    # =========================================================
    constraint_reports: List[ConstraintReport] = []
    for s in scenarios:
        cr = check_constraints(issue=issue, scenario=s, context=context, rules=rules)
        constraint_reports.append(cr)

    append_log(
        issue_id=issue.id,
        stage="constrained",
        payload={"constraint_reports": [cr.__dict__ for cr in constraint_reports]},
        log_chain=log_chain,
    )

    # Filter scenarios that passed OR are revisable with modifications
    cr_by_id = {cr.scenario_id: cr for cr in constraint_reports}
    viable = [s for s in scenarios if (cr_by_id.get(s.id) and (cr_by_id[s.id].passed or cr_by_id[s.id].required_modifications))]

    if not viable:
        append_log(
            issue_id=issue.id,
            stage="constraint_fail_all",
            payload={"note": "All scenarios failed constraints; requires redesign or scope revision."},
            log_chain=log_chain,
        )
        return {"status": "all_scenarios_failed_constraints", "issue_id": issue.id}

    # =========================================================
    # MODULE 5 — Participatory Deliberation Workspace
    # =========================================================
    incoming_objections: List[Objection] = collect_objections(issue.id)  # conceptual stub
    participant_notes: List[Dict[str, Any]] = collect_deliberation_notes(issue.id)  # conceptual stub

    deliberation_state = deliberate(
        issue=issue,
        scenarios=viable,
        context=context,
        constraint_reports=[cr_by_id[s.id] for s in viable if s.id in cr_by_id],
        incoming_objections=incoming_objections,
        participant_notes=participant_notes,
    )

    append_log(
        issue_id=issue.id,
        stage="deliberation",
        payload={"deliberation_state": deliberation_state.__dict__},
        log_chain=log_chain,
    )

    # =========================================================
    # MODULE 6 — Weighted Consensus Mechanism
    # =========================================================
    votes: List[Vote] = collect_votes(issue.id, deliberation_state.active_scenarios)  # stub
    participant_weights = {p.id: p.weight for p in participants}

    # Compute consensus per scenario; choose best candidate that isn't blocked
    consensus_results: List[ConsensusResult] = []
    for s in deliberation_state.active_scenarios:
        scenario_votes = [v for v in votes if v.scenario_id == s.id]
        scenario_objections = [o for o in deliberation_state.objections if o.scenario_id == s.id]

        res = compute_consensus(
            issue=issue,
            scenario=s,
            votes=scenario_votes,
            objections=scenario_objections,
            participant_weights=participant_weights,
            consensus_threshold=rules.get("consensus_threshold", 0.72),
            block_threshold=rules.get("block_threshold", 0.30),
        )
        consensus_results.append(res)

    append_log(
        issue_id=issue.id,
        stage="consensus_check",
        payload={"consensus_results": [r.__dict__ for r in consensus_results]},
        log_chain=log_chain,
    )

    # Choose a scenario:
    # - prefer directive=approve with highest consensus_score and lowest objection_index
    approved = [r for r in consensus_results if r.directive == "approve"]
    escalations = [r for r in consensus_results if r.directive == "escalate_to_module9"]

    chosen: Optional[ConsensusResult] = None
    if approved:
        approved.sort(key=lambda r: (r.consensus_score, -r.objection_index), reverse=True)
        chosen = approved[0]
    elif escalations:
        # pick the highest-consensus escalation
        escalations.sort(key=lambda r: r.consensus_score, reverse=True)
        chosen = escalations[0]
    else:
        # All require revision
        return {
            "status": "revise_and_retry",
            "issue_id": issue.id,
            "consensus_results": consensus_results,
        }

    chosen_scenario = next(s for s in deliberation_state.active_scenarios if s.id == chosen.scenario_id)

    # =========================================================
    # MODULE 9 — Human Deliberation & High-Bandwidth Resolution (if needed)
    # =========================================================
    module9_outcome: Optional[Module9Outcome] = None
    if chosen.directive == "escalate_to_module9":
        module9_outcome = run_high_bandwidth_deliberation(
            issue=issue,
            scenario=chosen_scenario,
            objections=[o for o in deliberation_state.objections if o.scenario_id == chosen_scenario.id],
            context=context,
        )

        append_log(
            issue_id=issue.id,
            stage="module9_outcome",
            payload={"module9_outcome": module9_outcome.__dict__},
            log_chain=log_chain,
        )

        # Apply modifications (if any) and continue to record/dispatch
        if module9_outcome.modifications:
            chosen_scenario = apply_modifications(chosen_scenario, module9_outcome.modifications)

    # =========================================================
    # MODULE 7 — Decision Recording, Versioning & Accountability
    # =========================================================
    decision = Decision(
        id=generate_id("decision"),
        issue_id=issue.id,
        scenario_id=chosen_scenario.id,
        status="approved",
        consensus_score=chosen.consensus_score,
        objection_index=chosen.objection_index,
        decided_at=datetime.utcnow(),
        rationale_hash=log_chain[-1].entry_hash if log_chain else "GENESIS",
        metadata={
            "consensus_result": chosen.__dict__,
            "module9_outcome": module9_outcome.__dict__ if module9_outcome else None,
        },
    )

    issue.status = "decided"
    issue.last_updated_at = datetime.utcnow()

    append_log(
        issue_id=issue.id,
        stage="decided",
        payload={"decision": decision.__dict__},
        log_chain=log_chain,
    )

    # =========================================================
    # MODULE 8 — Implementation Dispatch Interface
    # =========================================================
    dispatch = generate_dispatch(
        issue=issue,
        decision=decision,
        consensus=chosen,
        scenario=chosen_scenario,
        constraint_report=cr_by_id.get(chosen_scenario.id, ConstraintReport(issue_id=issue.id, scenario_id=chosen_scenario.id, passed=True)),
        cos_capacity_snapshot=cos_data.get("capacity_snapshot", {}),
    )

    append_log(
        issue_id=issue.id,
        stage="dispatched",
        payload={"dispatch": dispatch.__dict__},
        log_chain=log_chain,
    )

    return {
        "status": "approved_and_dispatched",
        "issue_id": issue.id,
        "decision": decision,
        "dispatch": dispatch,
        "structured_view": structured_view,
        "context": context,
        "constraint_reports": constraint_reports,
        "deliberation_state": deliberation_state,
        "consensus_results": consensus_results,
        "module9_outcome": module9_outcome,
        "review_outcome": review_outcome,
    }

```

***
