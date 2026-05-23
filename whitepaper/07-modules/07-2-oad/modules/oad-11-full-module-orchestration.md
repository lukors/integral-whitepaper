#### Putting It Together: OAD Orchestration

The function below shows, in compact form, how a single design concept moves through the **entire 10-module OAD pipeline**:

1. **Structured intake** (Module 1)
2. **Collaborative refinement** (Module 2)
3. **Material & ecological assessment** (Module 3)
4. **Lifecycle & maintainability modeling** (Module 4)
5. **Feasibility & constraint simulation** (Module 5)
6. **Skill & labor-step decomposition** (Module 6)
7. **Systems integration & architectural coordination** (Module 7)
8. **Optimization & efficiency improvement** (Module 8)
9. **Validation, certification & release** (Module 9)
10. **Knowledge commons & reuse repository** (Module 10)

The orchestration function does **not** show every possible branch or loop (e.g., multiple redesign cycles), but it makes clear that OAD is a **computable pipeline** from idea → certified design → global commons → COS/ITC inputs.

```python
from typing import Dict, Any, List, Optional
from datetime import datetime


def run_oad_pipeline(
    raw_spec_input: Dict[str, Any],
    author_id: str,
    node_registry: Dict[str, Any],
    eco_norm_refs: Dict[str, Dict[str, float]],
    certification_policy: Dict[str, Any],
    certifiers: List[str],
    frs_feedback: Optional[Dict[str, Any]] = None,
    iterations: int = 50,
) -> Dict[str, Any]:
    """
    End-to-end OAD flow for a single design concept.

    Modules touched:
    1) Design Submission & Structured Specification
    2) Collaborative Design Workspace (simplified here)
    3) Material & Ecological Coefficient Engine
    4) Lifecycle & Maintainability Modeling
    5) Feasibility & Constraint Simulation
    6) Skill & Labor-Step Decomposition
    7) Systems Integration & Architectural Coordination
    8) Optimization & Efficiency Engine
    9) Validation, Certification & Release Manager
    10) Knowledge Commons & Reuse Repository
    """

    # ---------------------------------------------
    # 1) Design Submission & Structured Specification
    # ---------------------------------------------
    spec, base_version = intake_design_submission(
        creator_id=author_id,
        title=raw_spec_input["title"],
        description=raw_spec_input["description"],
        payload=raw_spec_input["payload"],
        metadata=raw_spec_input.get("metadata", {}),
    )

    # ---------------------------------------------
    # 2) Collaborative Design Workspace (simplified)
    # ---------------------------------------------
    # In practice, branching/merging occurs here.
    working_version = base_version

    # ---------------------------------------------
    # 3) Material & Ecological Coefficient Engine
    # ---------------------------------------------
    material_profile, totals = build_material_profile(working_version)

    eco_assessment = compute_eco_assessment(
        version=working_version,
        norm_ref=eco_norm_refs,
        material_profile=material_profile,
        totals=totals,
        repairability_hint=0.5,                 # superseded by Module 4 later
        eco_threshold=certification_policy.get("eco_threshold", 0.5),
        frs_feedback=frs_feedback,              # optional FRS recalibration
    )

    if not eco_assessment.passed:
        return {
            "status": "rejected_ecology",
            "spec": spec,
            "version": working_version,
            "material_profile": material_profile,
            "eco_assessment": eco_assessment,
        }

    # ---------------------------------------------
    # 4) Lifecycle & Maintainability Modeling
    # ---------------------------------------------
    lifecycle_model = compute_lifecycle_model(
        version=working_version,
        eco_assessment=eco_assessment,
    )

    # ---------------------------------------------
    # 5) Feasibility & Constraint Simulation
    # ---------------------------------------------
    sim_result = run_feasibility_simulation(version=working_version)

    MIN_FEASIBILITY = certification_policy.get("min_feasibility", 0.6)
    if sim_result.feasibility_score < MIN_FEASIBILITY:
        return {
            "status": "rejected_feasibility",
            "spec": spec,
            "version": working_version,
            "eco_assessment": eco_assessment,
            "lifecycle": lifecycle_model,
            "simulation": sim_result,
        }

    # ---------------------------------------------
    # 6) Skill & Labor-Step Decomposition
    # ---------------------------------------------
    labor_profile = build_labor_profile(
        version=working_version,
        lifecycle=lifecycle_model,
    )

    # ---------------------------------------------
    # 7) Systems Integration & Architectural Coordination
    # ---------------------------------------------
    integration_check = evaluate_system_integration(
        version=working_version,
        node_registry=node_registry,
    )

    MIN_INTEGRATION_SCORE = certification_policy.get("min_integration_score", 0.6)
    if integration_check.integration_score < MIN_INTEGRATION_SCORE:
        return {
            "status": "rejected_integration",
            "spec": spec,
            "version": working_version,
            "eco_assessment": eco_assessment,
            "lifecycle": lifecycle_model,
            "simulation": sim_result,
            "labor_profile": labor_profile,
            "integration": integration_check,
        }

    # ---------------------------------------------
    # 8) Optimization & Efficiency Engine
    # ---------------------------------------------
    # Material intensity should be mass-based for optimization purposes.
    material_mass_kg = sum(material_profile.quantities_kg.values())

    opt_result, optimized_version = optimize_design(
        base_version=working_version,
        eco=eco_assessment,
        lifecycle=lifecycle_model,
        labor=labor_profile,
        sim=sim_result,
        integration=integration_check,
        material_intensity=material_mass_kg,
        iterations=iterations,
    )

    # Re-run key checks on optimized variant (best practice)
    material_profile_opt, totals_opt = build_material_profile(optimized_version)

    eco_opt = compute_eco_assessment(
        version=optimized_version,
        norm_ref=eco_norm_refs,
        material_profile=material_profile_opt,
        totals=totals_opt,
        repairability_hint=0.5,
        eco_threshold=certification_policy.get("eco_threshold", 0.5),
        frs_feedback=frs_feedback,
    )

    lifecycle_opt = compute_lifecycle_model(
        version=optimized_version,
        eco_assessment=eco_opt,
    )

    sim_opt = run_feasibility_simulation(version=optimized_version)

    labor_opt = build_labor_profile(
        version=optimized_version,
        lifecycle=lifecycle_opt,
    )

    integration_opt = evaluate_system_integration(
        version=optimized_version,
        node_registry=node_registry,
    )

    def can_proceed(eco: EcoAssessment, sim: SimulationResult, integ: IntegrationCheck) -> bool:
        return (
            eco.passed
            and sim.feasibility_score >= MIN_FEASIBILITY
            and integ.integration_score >= MIN_INTEGRATION_SCORE
            and not integ.conflicts
        )

    if can_proceed(eco_opt, sim_opt, integration_opt):
        decision_version = optimized_version
        final_material_profile = material_profile_opt
        final_eco = eco_opt
        final_lifecycle = lifecycle_opt
        final_sim = sim_opt
        final_labor = labor_opt
        final_integration = integration_opt
        used_optimized = True
    else:
        decision_version = working_version
        final_material_profile = material_profile
        final_eco = eco_assessment
        final_lifecycle = lifecycle_model
        final_sim = sim_result
        final_labor = labor_profile
        final_integration = integration_check
        used_optimized = False

    # ---------------------------------------------
    # 9) Validation, Certification & Release Manager
    # ---------------------------------------------
    cert_record = certify_design_version(
        version=decision_version,
        eco=final_eco,
        lifecycle=final_lifecycle,
        labor=final_labor,
        sim=final_sim,
        integration=final_integration,
        certifiers=certifiers,
        policy=certification_policy,
    )

    if cert_record.status != "certified":
        return {
            "status": "not_certified",
            "spec": spec,
            "final_version": decision_version,
            "used_optimized": used_optimized,
            "eco_assessment": final_eco,
            "lifecycle": final_lifecycle,
            "simulation": final_sim,
            "labor_profile": final_labor,
            "integration": final_integration,
            "optimization": opt_result,
            "certification": cert_record,
        }

    # Build COS/ITC valuation payload (matches the declared OADValuationProfile fields)
    usage = decision_version.parameters.get("usage_assumptions", {"hours_per_day": 4.0, "days_per_year": 250})
    hours_per_year = usage["hours_per_day"] * usage["days_per_year"]
    expected_lifespan_hours = final_lifecycle.expected_lifetime_years * hours_per_year

    valuation_profile = OADValuationProfile(
        version_id=decision_version.id,
        material_intensity_norm=certification_policy.get("material_norm_fn", lambda x: x)(sum(final_material_profile.quantities_kg.values())),
        ecological_score=final_eco.eco_score,
        bill_of_materials=dict(final_material_profile.quantities_kg),
        embodied_energy_mj=final_material_profile.embodied_energy_mj,
        embodied_carbon_kg=final_material_profile.embodied_carbon_kg,
        expected_lifespan_hours=expected_lifespan_hours,
        production_labor_hours=final_labor.total_production_hours,
        maintenance_labor_hours_over_life=final_labor.total_maintenance_hours_over_life,
        hours_by_skill_tier=dict(final_labor.hours_by_skill_tier),
        notes="Generated at certification time from OAD modules 3–7 (and revalidated after optimization).",
    )

    # ---------------------------------------------
    # 10) Knowledge Commons & Reuse Repository
    # ---------------------------------------------
    climates = decision_version.parameters.get("target_climates", [])
    sectors = decision_version.parameters.get("sectors", [])
    tags = decision_version.parameters.get("tags", [])

    repo_entry = publish_to_repository(
        version=decision_version,
        spec=spec,
        certification=cert_record,
        climates=climates,
        sectors=sectors,
        tags=tags,
    )

    return {
        "status": "certified",
        "spec": spec,
        "final_version": decision_version,
        "used_optimized": used_optimized,
        "material_profile": final_material_profile,
        "eco_assessment": final_eco,
        "lifecycle": final_lifecycle,
        "simulation": final_sim,
        "labor_profile": final_labor,
        "integration": final_integration,
        "optimization": opt_result,
        "certification": cert_record,
        "valuation_profile": valuation_profile,
        "repo_entry": repo_entry,
    }
```

In other words, every design that enters Integral passes through a finite, auditable, computable pipeline—from structured idea to ecological evaluation, from lifecycle modeling to labor decomposition, from feasibility and integration checks to optimization and certification, and finally into a global knowledge commons that feeds COS and ITC with grounded physical intelligence rather than abstract prices.

Finally, every certified design re-enters OAD through Module 10, where reuse data, operational feedback, and contextual adaptations recursively feed back into Module 2—ensuring that Integral’s design intelligence continuously evolves through real-world learning rather than static specification.

***
