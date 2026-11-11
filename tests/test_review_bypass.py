"""Admin review bypass refuses any merge requirement besides the review."""

from pathlib import Path

import pytest
import review_bypass
import shipping
from gate_config import JsonValue
from test_shipping import (
    _OWNER,
    _PR_URL,
    _UNDO,
    FakeGitHub,
    _check,
    _fixture,
    _patch_gh,
    _pull,
    _ready_fixture,
    _ready_outcome,
    _review,
)

EMPTY: JsonValue = {"totalCount": 0, "nodes": []}


def nodes(*items: JsonValue) -> JsonValue:
    return {"totalCount": len(items), "nodes": list(items)}


def protection(**changes: JsonValue) -> JsonValue:
    rule: dict[str, JsonValue] = {
        "requiresCommitSignatures": False,
        "requiresDeployments": False,
        "lockBranch": False,
        "requiresStrictStatusChecks": False,
    }
    return {"branchProtectionRule": rule | changes, "rules": EMPTY}


def required_rule(context: str, strict: JsonValue = False) -> JsonValue:
    parameters: dict[str, JsonValue] = {"requiredStatusChecks": [{"context": context}]}
    if strict is not None:
        parameters["strictRequiredStatusChecksPolicy"] = strict
    rule: JsonValue = {"type": "REQUIRED_STATUS_CHECKS", "parameters": parameters}
    return {"branchProtectionRule": None, "rules": nodes(rule)}


def ruleset(*types: str) -> JsonValue:
    rules: list[JsonValue] = [{"type": kind} for kind in types]
    return {"rules": nodes(*rules)}


BUILD: JsonValue = {"name": "build", "conclusion": "SUCCESS"}


@pytest.mark.parametrize(
    ("pull", "contexts", "message"),
    [
        ({}, nodes(BUILD), None),
        ({"isMergeQueueEnabled": True}, nodes(BUILD), "merge queue"),
        ({"isMergeQueueEnabled": None}, nodes(BUILD), "merge queue"),
        ({"baseRef": None}, nodes(BUILD), "unreadable"),
        ({"baseRef": {"rules": {"totalCount": 101, "nodes": []}}}, EMPTY, "unreadable"),
        ({"baseRef": protection()}, nodes(BUILD), None),
        ({"baseRef": protection(requiresCommitSignatures=True)}, EMPTY, "protection"),
        ({"baseRef": protection(requiresDeployments=True)}, EMPTY, "protection"),
        ({"baseRef": protection(lockBranch=None)}, EMPTY, "protection"),
        ({"baseRef": protection(requiresStrictStatusChecks=True)}, EMPTY, "protection"),
        ({"baseRef": ruleset("PULL_REQUEST", "DELETION")}, EMPTY, None),
        ({"baseRef": ruleset("CODE_SCANNING")}, EMPTY, "CODE_SCANNING"),
        ({"baseRef": ruleset("MERGE_QUEUE")}, EMPTY, "MERGE_QUEUE"),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            nodes(BUILD),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["security"])},
            nodes(BUILD),
            "required check has not passed: security",
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            nodes({"name": "build", "conclusion": "SKIPPED"}),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["ci/legacy"])},
            nodes({"context": "ci/legacy", "state": "SUCCESS"}),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            {"totalCount": 2, "nodes": [BUILD]},
            "required check",
        ),
        ({"baseRef": required_rule("build")}, nodes(BUILD), None),
        ({"baseRef": required_rule("security")}, nodes(BUILD), "security"),
        ({"baseRef": required_rule("build", True)}, nodes(BUILD), "up to date"),
        ({"baseRef": required_rule("build", None)}, nodes(BUILD), "up to date"),
    ],
)
def test_bypass_needs_every_other_merge_requirement_satisfied(
    pull: dict[str, JsonValue], contexts: JsonValue, message: str | None
) -> None:
    review: dict[str, JsonValue] = {
        "isMergeQueueEnabled": False,
        "reviewThreads": EMPTY,
        "baseRef": {"branchProtectionRule": None, "rules": EMPTY},
    }
    problem = review_bypass._other_merge_requirement(
        review | pull, {"state": "SUCCESS", "contexts": contexts}
    )
    if message is None:
        assert problem is None
    else:
        assert problem is not None and message in problem


@pytest.mark.parametrize(
    ("state", "threads"),
    [
        ("clean", nodes({"isResolved": False})),
        ("clean", {"totalCount": 2, "nodes": [{"isResolved": True}]}),
        ("blocked", nodes({"isResolved": False})),
    ],
)
def test_ready_refuses_an_open_or_uncounted_review_thread_on_every_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str, threads: JsonValue
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, mergeable_state=state), [_check(fixture.head)])
    fake.review = _review(fixture.head, reviewThreads=threads)
    monkeypatch.setattr(shipping, "gh", fake)
    with pytest.raises(shipping.ShippingError, match="review conversation"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


@pytest.mark.parametrize(
    ("comparison", "message"),
    [
        ({"behind_by": 0}, None),
        ({"behind_by": 2}, "2 commit\\(s\\) behind main; rebase"),
        ({"behind_by": None}, "comparison with its base is invalid"),
        ({"behind_by": True}, "comparison with its base is invalid"),
        ({}, "comparison with its base is invalid"),
    ],
)
def test_ready_refuses_a_pr_behind_its_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    comparison: object,
    message: str | None,
) -> None:
    fixture, fake = _ready_fixture(tmp_path, monkeypatch)
    fake.comparison = comparison
    if message is not None:
        with pytest.raises(shipping.ShippingError, match=message):
            shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
        return
    shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert any(
        call[-1] == f"repos/acme/widget/compare/main...{fixture.head}"
        for call in fake.calls
    )


@pytest.mark.parametrize(
    ("body", "passes"),
    [
        (_UNDO, True),
        (f"Summary\r\n\r\n{_UNDO}\r\n", True),
        ("", False),
        ("Undo:", False),
        ("Undo:   \nNext line", False),
        ("We can undo this later.", False),
    ],
)
def test_ready_requires_an_undo_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, passes: bool
) -> None:
    fixture = _fixture(tmp_path)
    _patch_gh(
        monkeypatch, FakeGitHub(_pull(fixture, body=body), [_check(fixture.head)])
    )
    if passes:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
        return
    with pytest.raises(shipping.ShippingError, match="starts `Undo:`"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


_PEER = {"login": "peer", "permissions": {"push": True}}


def _code_owner_review(head: str, required: bool = True) -> object:
    rule = {"type": "PULL_REQUEST", "parameters": {"requireCodeOwnerReview": required}}
    return _review(
        head, baseRefName="main", baseRef={"rules": {"totalCount": 1, "nodes": [rule]}}
    )


@pytest.mark.parametrize(
    ("codeowners", "required", "message"),
    [
        ({".github/CODEOWNERS": "* @owner\n"}, True, None),
        ({"CODEOWNERS": "# all files\n*  @Owner\n/docs/ @owner # docs\n"}, True, None),
        ({".github/CODEOWNERS": "* @owner\n"}, False, "another"),
        ({".github/CODEOWNERS": "* @owner @peer\n"}, True, "another"),
        ({".github/CODEOWNERS": "* @owner\n/docs/\n"}, True, "another"),
        ({".github/CODEOWNERS": "/src/ @owner\n"}, True, "another"),
        ({".github/CODEOWNERS": "* @acme/maintainers\n"}, True, "another"),
        ({}, True, "another"),
    ],
)
def test_ready_bypasses_a_code_owner_review_only_the_author_can_give(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    codeowners: dict[str, str],
    required: bool,
    message: str | None,
) -> None:
    fixture = _fixture(tmp_path)
    pull = _pull(fixture, mergeable_state="blocked", mergeable=True)
    fake = FakeGitHub(pull, [_check(fixture.head)])
    fake.review = _code_owner_review(fixture.head, required)
    fake.collaborators = [[_OWNER, _PEER]]
    fake.codeowners = codeowners
    shipment = _ready_outcome(fixture, fake, monkeypatch, message)
    assert (shipment is None) is (message is not None)
    assert shipment is None or shipment.review_bypass is True


@pytest.mark.parametrize(
    ("state", "threads", "others", "message"),
    [
        ("blocked", [], [], None),
        ("blocked", [{"isResolved": False}], [], "conversation"),
        ("blocked", [], [_PEER], "another"),
        ("clean", [], [], "not blocked"),
    ],
)
def test_author_only_review_block_reads_the_open_pull_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    threads: list[object],
    others: list[object],
    message: str | None,
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, mergeable_state=state), [])
    fake.review = _review(
        fixture.head, reviewThreads={"totalCount": len(threads), "nodes": threads}
    )
    fake.collaborators = [[_OWNER, *others]]
    _patch_gh(monkeypatch, fake)
    problem = review_bypass.author_only_review_block(
        fixture.root, _PR_URL, fixture.head
    )
    if message is None:
        assert problem is None
    else:
        assert problem is not None and message in problem


_RULES_URL = "https://github.com/acme/widget/settings/rules"
_NO_RULE: JsonValue = {"branchProtectionRule": None, "rules": EMPTY}
_UNREADABLE = (
    "Not checked: whether main requires build (the base branch rules are "
    "unreadable or incomplete)."
)


def update_rule(*contexts: str, rules: JsonValue = EMPTY) -> JsonValue:
    seen: JsonValue = {"requiredStatusCheckContexts": list(contexts)}
    return {"branchProtectionRule": None, "refUpdateRule": seen, "rules": rules}


def rules_answer(base: JsonValue, admin: bool = True) -> JsonValue:
    pull: JsonValue = {"baseRef": base}
    repository: JsonValue = {"viewerCanAdminister": admin, "pullRequest": pull}
    return {"data": {"repository": repository}}


def _rule_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: JsonValue
) -> tuple[str | None, FakeGitHub]:
    fixture, fake = _ready_fixture(tmp_path, monkeypatch)
    fake.rules = answer
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    return shipment.rule_note, fake


@pytest.mark.parametrize(
    "base",
    [_NO_RULE, protection(requiredStatusCheckContexts=[]), required_rule("lint")],
)
def test_ship_ready_warns_when_the_base_branch_does_not_require_a_shipping_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base: JsonValue
) -> None:
    note, _ = _rule_note(tmp_path, monkeypatch, rules_answer(base))
    assert note == (
        "Warning: main does not require build, so a PR can merge while that check "
        f"is missing or failed. A repository admin adds it at {_RULES_URL} "
        "(branch ruleset for main, Require status checks to pass, add build)."
    )


@pytest.mark.parametrize(
    ("base", "admin"),
    [
        (protection(requiredStatusCheckContexts=["build"]), True),
        (required_rule("build"), True),
        (required_rule("build"), False),
    ],
)
def test_ship_ready_is_silent_when_protection_or_a_ruleset_requires_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base: JsonValue, admin: bool
) -> None:
    note, _ = _rule_note(tmp_path, monkeypatch, rules_answer(base, admin))
    assert note is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (
            rules_answer(_NO_RULE, admin=False),
            _UNREADABLE,
        ),
        (
            rules_answer(
                {"branchProtectionRule": None, "rules": {"totalCount": 2, "nodes": []}}
            ),
            (
                "Not checked: whether main requires build (the base branch rules "
                "are unreadable or incomplete)."
            ),
        ),
        (
            rules_answer(None),
            (
                "Not checked: whether main requires build (the base branch rules "
                "are unreadable or incomplete)."
            ),
        ),
        (
            {"errors": [{"message": "denied"}]},
            "Not checked: whether main requires build (review data must be an object).",
        ),
    ],
)
def test_ship_ready_says_not_checked_for_a_non_admin_or_incomplete_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: JsonValue,
    expected: str,
) -> None:
    note, _ = _rule_note(tmp_path, monkeypatch, answer)
    assert note == expected


def test_ship_ready_adds_exactly_one_branch_rule_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, fake = _rule_note(tmp_path, monkeypatch, rules_answer(required_rule("build")))
    queries = [call[-1] for call in fake.calls if call[1] == "graphql"]
    assert len(queries) == 2
    assert sum("viewerCanAdminister" in query for query in queries) == 1


def _refused_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base: JsonValue
) -> tuple[str, FakeGitHub]:
    fixture = _fixture(tmp_path)
    queued = _check(fixture.head, status="queued", conclusion=None, completed_at=None)
    fake = FakeGitHub(_pull(fixture), [queued])
    fake.rules = rules_answer(base)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.PendingCheck) as refused:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    return str(refused.value), fake


def test_a_refused_ready_run_shows_the_branch_rule_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    message, fake = _refused_run(tmp_path, monkeypatch, _NO_RULE)
    refusal, _, warning = message.partition("\n")
    assert refusal == "required check has not completed: build"
    assert warning.startswith("Warning: main does not require build, so")
    queries = [call[-1] for call in fake.calls if call[1] == "graphql"]
    assert sum("viewerCanAdminister" in query for query in queries) == 1


def test_a_refused_ready_run_shows_only_the_refusal_when_the_base_requires_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    message, _ = _refused_run(tmp_path, monkeypatch, required_rule("build"))
    assert message == "required check has not completed: build"


_ASK = (
    "Warning: main does not require build, so a PR can merge while that check is "
    f"missing or failed. Ask a repository admin to add it at {_RULES_URL} "
    "(branch ruleset for main, Require status checks to pass, add build)."
)


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        (update_rule("build"), None),
        (update_rule("lint"), _ASK),
        (update_rule(), _ASK),
        (_NO_RULE, _UNREADABLE),
        (update_rule(rules={"totalCount": 2, "nodes": []}), _UNREADABLE),
        (None, _UNREADABLE),
    ],
)
def test_ship_ready_decides_for_a_non_admin_from_the_rules_it_can_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    base: JsonValue,
    expected: str | None,
) -> None:
    note, _ = _rule_note(tmp_path, monkeypatch, rules_answer(base, admin=False))
    assert note == expected


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        (
            {"branchProtectionRule": None, "rules": nodes({"type": "WORKFLOWS"})},
            "Not checked: whether main requires build "
            "(a required workflow rule may enforce it).",
        ),
        (
            {
                "branchProtectionRule": {"requiredStatusCheckContexts": ["build"]},
                "rules": nodes({"type": "WORKFLOWS"}),
            },
            None,
        ),
    ],
)
def test_ship_ready_does_not_warn_when_a_required_workflow_rule_may_enforce_the_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    base: JsonValue,
    expected: str | None,
) -> None:
    note, _ = _rule_note(tmp_path, monkeypatch, rules_answer(base))
    assert note == expected
