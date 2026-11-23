"""The quick judgements of a push whose full check is left to CI: plan stage, plan records and changed-line text rules."""

import os
from pathlib import Path


def push_text_checks(root: Path, base: str | None) -> int:
    from ci_setup import push_base, require_ci_base

    require_ci_base(base, root)
    base = push_base(root, base)
    try:
        import change_size
        import plans
        from comments import validate_rules

        change_size.judged_stage(root, base, "Complete")
        plans.validate_records(root, base)
        changed_names = validate_rules(root, base)
        if not os.environ.get("GITHUB_ACTIONS") and not os.environ.get("CI"):
            from local_ui_proof import validate_local_ui_proof

            validate_local_ui_proof(root, base, changed_names)
    except ValueError as error:
        print(f"Hard Eng: {error}")
        return 1
    print("Hard Eng: the plan checks and the changed-line text rules passed.")
    return 0
