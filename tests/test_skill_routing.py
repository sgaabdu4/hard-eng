"""Word overlap between sample requests and skill descriptions approximates, but does not prove, how a model picks a skill."""

import math
import re
from collections import Counter
from pathlib import Path

import yaml
from conftest import SOURCE

WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    WORD.findall(
        "a an and are as at be by can do does for from has have how i in into is it its me my of on or our so than that the their them then there these this to up use used using we what when where which while with without you your not no also before after through across skip"
    )
)
MAX_SIMILARITY = 0.4

ROUTES = [
    ("Plan the change before we write any code for the new export feature", "he-plan"),
    (
        "Write a plan for the login rework and settle the open product decisions",
        "he-plan",
    ),
    ("Draft a compact plan for renaming the settings option", "he-plan"),
    ("The plan is approved, implement it and run the integrated checks", "he-build"),
    ("Continue building from the ready plan and fix what the checks find", "he-build"),
    ("Fix this bug and verify it with the checks until the build is ready", "he-build"),
    (
        "Open a pull request for this task branch and merge it once it is green",
        "he-ship",
    ),
    ("Ship this: create the PR, check the remote result and clean up", "he-ship"),
    ("Release and deploy the verified build through a pull request", "he-ship"),
    (
        "The same failure keeps recurring, so record a lasting decision as an ADR",
        "he-learn",
    ),
    (
        "Capture this accepted decision durably so the repeated failures stop",
        "he-learn",
    ),
    ("Review the latest commit for defects", "code-review"),
    (
        "Review this PR and challenge whether the changes match the intended behavior",
        "code-review",
    ),
    (
        "Check the working tree changes for concrete defects before I merge",
        "code-review",
    ),
    ("Prove the checkout journey works end to end in the browser", "e2e"),
    (
        "Run end-to-end verification of the signup flow across the mobile app and API",
        "e2e",
    ),
    ("Give me visual proof of the runtime UI using the existing test tools", "e2e"),
    (
        "Research which library to use and verify the current facts before recommending one",
        "research",
    ),
    (
        "Investigate the codebase and compare the two approaches before we decide",
        "research",
    ),
    (
        "Research why this failure happens and check the external documentation",
        "research",
    ),
    (
        "Do a security review of the new upload endpoint for injection and authorization risks",
        "security-review",
    ),
    (
        "Review this change touching a trust boundary for secret and data exposure",
        "security-review",
    ),
    ("Check the LLM tool configuration for security risks", "security-review"),
    (
        "Design the module ownership and public interface for the billing domain",
        "codebase-design",
    ),
    (
        "Where should the UI tokens and components live, and who owns them?",
        "codebase-design",
    ),
    (
        "Model the bounded contexts and invariants of the ordering domain",
        "codebase-design",
    ),
    (
        "Write a new skill package with a SKILL.md for our release process",
        "writing-great-skills",
    ),
    (
        "Review and revise this agent skill so it triggers properly",
        "writing-great-skills",
    ),
    (
        "Revise the skill description and SKILL.md of an existing agent skill",
        "writing-great-skills",
    ),
    (
        "Migrate the Appwrite production database and wire the MCP server",
        "appwrite-backend",
    ),
    (
        "Self-host Appwrite and write SDK code for the account erasure flow",
        "appwrite-backend",
    ),
    (
        "Add a Riverpod provider to the Flutter app architecture",
        "building-flutter-apps",
    ),
    (
        "Build the Windows installer and update pipeline for the Flutter desktop app",
        "building-flutter-apps",
    ),
]
NEAR_MISSES = [
    ("Review the latest commit for defects", "he-build"),
    ("Review the latest commit for defects", "he-ship"),
    ("Plan the change before we write any code for the new export feature", "he-build"),
    (
        "Open a pull request for this task branch and merge it once it is green",
        "he-plan",
    ),
    (
        "Do a security review of the new upload endpoint for injection and authorization risks",
        "code-review",
    ),
    ("Prove the checkout journey works end to end in the browser", "he-ship"),
    (
        "Build the Windows installer and update pipeline for the Flutter desktop app",
        "appwrite-backend",
    ),
    (
        "Migrate the Appwrite production database and wire the MCP server",
        "building-flutter-apps",
    ),
]


def descriptions(root: Path) -> dict[str, str]:
    """Descriptions of the skills a model may invoke on its own."""
    found: dict[str, str] = {}
    for skill in sorted((root / ".agents/skills").iterdir()):
        head = (skill / "SKILL.md").read_text().split("---\n")[1]
        fields: dict[str, object] = yaml.safe_load(head)
        if not fields.get("disable-model-invocation"):
            found[skill.name] = str(fields["description"])
    return found


def stem(word: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", word) if len(word) > 4 else word


def words(text: str) -> list[str]:
    return [stem(w) for w in WORD.findall(text.lower()) if w not in STOPWORDS]


class Index:
    def __init__(self, texts: dict[str, str]) -> None:
        self.counts = {name: Counter(words(text)) for name, text in texts.items()}
        frequency = Counter(w for count in self.counts.values() for w in count)
        total = len(texts)
        self.idf = {
            w: math.log((1 + total) / (1 + n)) + 1 for w, n in frequency.items()
        }
        self.vectors = {name: self.weigh(count) for name, count in self.counts.items()}

    def weigh(self, count: Counter[str]) -> dict[str, float]:
        return {w: n * self.idf[w] for w, n in count.items() if w in self.idf}

    def scores(self, request: str) -> dict[str, float]:
        query = self.weigh(Counter(words(request)))
        return {name: cosine(query, vector) for name, vector in self.vectors.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    dot = sum(v * right.get(w, 0.0) for w, v in left.items())
    norm = math.sqrt(sum(v * v for v in left.values())) * math.sqrt(
        sum(v * v for v in right.values())
    )
    return dot / norm if norm else 0.0


def ranked(index: Index, request: str) -> list[str]:
    scores = index.scores(request)
    return sorted(scores, key=lambda name: (-scores[name], name))


def similar_pairs(index: Index) -> list[tuple[float, str, str]]:
    names = sorted(index.vectors)
    return sorted(
        (cosine(index.vectors[a], index.vectors[b]), a, b)
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    )[::-1]


def routing_failures(index: Index) -> list[str]:
    failures = [
        f"{request!r}: expected {skill}, ranked {ranked(index, request)[0]} first"
        for request, skill in ROUTES
        if ranked(index, request)[0] != skill
    ]
    failures += [
        f"{request!r}: must not pick {skill}"
        for request, skill in NEAR_MISSES
        if ranked(index, request)[0] == skill
    ]
    return failures


def similarity_failures(index: Index) -> list[str]:
    return [
        f"{a} and {b} are {score:.2f} alike (limit {MAX_SIMILARITY})"
        for score, a, b in similar_pairs(index)
        if score > MAX_SIMILARITY
    ]


def test_every_request_picks_its_own_skill() -> None:
    assert routing_failures(Index(descriptions(SOURCE))) == []


def test_no_two_descriptions_are_too_alike() -> None:
    assert similarity_failures(Index(descriptions(SOURCE))) == []


def test_each_model_invocable_skill_has_several_sample_requests() -> None:
    owners = Counter(skill for _, skill in ROUTES)
    known = set(descriptions(SOURCE))
    assert set(owners) <= known
    assert [skill for skill in sorted(known - {"he"}) if owners[skill] < 2] == []


def test_misrouting_and_overlapping_descriptions_are_caught() -> None:
    texts = {
        "he-plan": "Plan a change before implementation.",
        "he-build": "Implement a ready plan.",
        "he-ship": "Deliver a verified build through a pull request.",
        "he-copy": "Deliver a verified build through a pull request.",
    }
    index = Index(texts)

    assert routing_failures(index)
    assert similarity_failures(index) == [
        "he-copy and he-ship are 1.00 alike (limit 0.4)"
    ]
