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
)
