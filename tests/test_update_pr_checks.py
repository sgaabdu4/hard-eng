import pytest
import update_pr
from gate_config import JsonValue

TEXT_RUN: dict[str, JsonValue] = {
    "workflowName": "PR text",
    "name": "pr text",
    "status": "COMPLETED",
}
CANCELLED: dict[str, JsonValue] = {"conclusion": "CANCELLED"}
PASSED: dict[str, JsonValue] = {"conclusion": "SUCCESS"}


@pytest.mark.parametrize(
    ("first", "second", "state"),
    [
        (CANCELLED, PASSED, "passing"),
        (PASSED, CANCELLED, "passing"),
        (CANCELLED, {"status": "QUEUED", "conclusion": ""}, "pending"),
        (CANCELLED, {"conclusion": "FAILURE"}, "failing"),
        ({"conclusion": "FAILURE"}, PASSED, "failing"),
        (CANCELLED, CANCELLED, "failing"),
        (CANCELLED, {"conclusion": "SKIPPED"}, "failing"),
        (CANCELLED | {"workflowName": "Deploy"}, PASSED, "failing"),
        (CANCELLED | {"workflowName": ""}, PASSED | {"workflowName": ""}, "failing"),
    ],
)
def test_update_pr_takes_no_verdict_from_a_cancelled_run_of_a_check_that_ran_again(
    first: dict[str, JsonValue], second: dict[str, JsonValue], state: str
) -> None:
    pull: dict[str, JsonValue] = {
        "statusCheckRollup": [TEXT_RUN | first, TEXT_RUN | second]
    }
    assert update_pr.check_state(pull) == state
