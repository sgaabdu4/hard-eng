import os
from pathlib import Path


def repository_root() -> Path:
    if os.environ.get("MUTANT_UNDER_TEST") is None:
        return Path(__file__).resolve().parents[1]
    mutated = Path.cwd()
    if mutated.name != "mutants" or not (mutated / "skills" / "deterministic-checks" / "scripts").is_dir():
        raise RuntimeError(f"mutmut must run tests from its mutants tree, not {mutated}")
    return mutated


ROOT = repository_root()
HE = ROOT / "skills" / "he" / "scripts"
CHECKS = ROOT / "skills" / "deterministic-checks" / "scripts"

SCRIPTS = ROOT / "scripts"

IN_PROCESS = (
    SCRIPTS / "managed-skill-update-state-regression.py",
    CHECKS / "script_runner_regression_check.py",
    CHECKS / "bounded_run_regression_check.py",
    CHECKS / "github_delivery_regression_check.py",
    CHECKS / "dart_decimate_gate_regression_check.py",
    CHECKS / "source_tree_coordination_regression_check.py",
    CHECKS / "project_gate_regression_check.py",
    CHECKS / "slice_gate_regression_check.py",
    HE / "plan_steps_regression.py",
    HE / "build_steps_regression.py",
    HE / "plan_cleanup_regression.py",
    HE / "protected_direct_regression.py",
    HE / "execution_evidence_regression.py",
    HE / "setup_state_regression.py",
    HE / "ticket_state_regression.py",
    HE / "lifecycle_excludes_regression.py",
    CHECKS / "privacy_scan_regression_check.py",
    CHECKS / "mutation_ledger_regression_check.py",
    CHECKS / "lifecycle_guard_regression_check.py",
    CHECKS / "external_cli_restore_regression_check.py",
    CHECKS / "final_concerns_contract_regression_check.py",
    CHECKS / "git_env_cache_regression_check.py",
    CHECKS / "structured_output_regression_check.py",
    HE / "external_claims_regression.py",
    HE / "skill_source_policy_regression.py",
    HE / "tracker_github_regression.py",
    HE / "tracker_http_regression.py",
    ROOT / "skills" / "he-learn" / "scripts" / "learning_state_regression.py",
    ROOT / "skills" / "adversarial-review" / "scripts" / "run_review_regression.py",
    SCRIPTS / "worktree-policy-contract-check.py",
    SCRIPTS / "worktree-readiness-contracts.py",
    SCRIPTS / "context-docs-contracts.py",
    SCRIPTS / "machine-scope-guard-contract.py",
    SCRIPTS / "protected-planning-contract-check.py",
    SCRIPTS / "checkpoint-receipt-paths-contract-check.py",
    SCRIPTS / "inprocess-seam-contract.py",
    SCRIPTS / "bounded-operations-contract.py",
    SCRIPTS / "rollout-shared-contract-check.py",
    SCRIPTS / "rollout-workflow-contract-check.py",
    SCRIPTS / "json-style-contract.py",
    SCRIPTS / "route_resource_contracts.py",
)
