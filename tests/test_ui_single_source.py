"""The whole-project UI pass: raw values and base elements outside the library."""

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
import shipping
import yaml
from comments import validate_rules
from conftest import commit, gate, init
from ui_exempt import exemption
from ui_library import expected_index, index_text
from ui_tokens import token_facts, token_findings
from ui_whole import (
    native_findings,
    token_file,
)
from whole_project import text_files, validate_whole_project

FIXTURES = Path(__file__).parent / "fixtures/ui_single_source"
POLICY: dict[str, object] = {
    "base": "main",
    "checks": ["hard-eng"],
    "ui_paths": ["src/**"],
    "ui_library": ["src/ui/*"],
    "ci_seconds": 180,
    "pre_push_seconds": 180,
    "delivery": [],
}


def write_design(texts: dict[str, str], root: Path) -> None:
    facts = token_facts(
        [
            text
            for name, text in texts.items()
            if name.endswith(".css") and token_file(name, text)
        ]
    )
    colours = {
        f"c{i}": "#" + value[:6] + ("" if value[6:] == "ff" else value[6:])
        for i, value in enumerate(sorted(facts.colours))
    }
    spacing = {f"s{i}": f"{value:g}px" for i, value in enumerate(sorted(facts.lengths))}
    typography = {
        f"t{i}": {"fontFamily": value} for i, value in enumerate(sorted(facts.families))
    }
    data = {"colors": colours, "spacing": spacing, "typography": typography}
    (root / "DESIGN.md").write_text(f"---\n{yaml.safe_dump(data)}---\n\n# Fixture\n")


def reindex(root: Path) -> None:
    texts = text_files(root)
    write_design(texts, root)
    library = json.loads((root / "hard-eng.gates.json").read_text())["shipping"][
        "ui_library"
    ]
    uses = {
        entry: dict.fromkeys(parts, "a part")
        for entry, parts in expected_index(texts, library).items()
    }
    (root / "UI-LIBRARY.md").write_text(index_text(texts, library, uses))


def build(tmp_path: Path, fixture: str, index: bool = True, **policy: object) -> Path:
    root = tmp_path / fixture
    tmp_path.mkdir(parents=True, exist_ok=True)
    init(root)
    shutil.copytree(FIXTURES / fixture, root, dirs_exist_ok=True)
    (root / "hard-eng.gates.json").write_text(json.dumps({"shipping": POLICY | policy}))
    (root / "README.md").write_text("fixture, parts in UI-LIBRARY.md\n")
    if index:
        reindex(root)
    else:
        write_design(text_files(root), root)
    return root


def refusal(root: Path) -> str:
    with pytest.raises(ValueError) as error:
        validate_whole_project(root)
    return str(error.value)


def hits(message: str, word: str) -> Counter[str]:
    return Counter(re.findall(rf"(\S+?:\d+): {word} \((.*?)\) outside", message))


def typed(message: str, kind: str) -> Counter[str]:
    return Counter(
        re.findall(
            rf"(\S+?:\d+): a {kind} typed in the file \((.*?)\)\. [A-Z]", message
        )
    )


def test_base_elements_only_in_library(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a base element outside the library fails; the library may hold one."""
    red = refusal(build(tmp_path, "web-red"))
    found = Counter(
        (name.split(":")[0], tag)
        for name, tag in hits(red, "a base element").elements()
    )
    assert found == Counter(
        {
            ("src/screens/Login.tsx", "<input"): 1,
            ("src/screens/Login.tsx", "<textarea"): 1,
            ("src/screens/Login.tsx", "<select"): 1,
            ("src/screens/Login.tsx", "<button"): 1,
            ("src/screens/Login.tsx", "<dialog"): 1,
            ("src/screens/page.ts", "<button"): 1,
            ("src/screens/page.ts", "createElement('input')"): 1,
        }
    )
    validate_whole_project(build(tmp_path, "web-fixed"))


def test_web_raw_values_red_then_fixed(tmp_path: Path) -> None:
    """HE-UI-SOURCE: each raw colour or size is one finding, even in the library; tokens and precise forms pass."""
    red = refusal(build(tmp_path, "web-red"))
    found = Counter(
        (name.split(":")[0], text)
        for kind in ("colour", "size")
        for name, text in typed(red, kind).elements()
    )
    assert found == Counter(
        {
            ("src/screens/Profile.tsx", "bg-[#1a2b3c]"): 1,
            ("src/screens/Profile.tsx", "rgb("): 1,
            ("src/screens/Profile.tsx", "p-[13px]"): 1,
            ("src/screens/Profile.tsx", "w-[240px]"): 1,
            ("src/screens/Profile.tsx", "h-[3rem]"): 1,
            ("src/screens/Profile.tsx", "rounded-[7px]"): 1,
            ("src/screens/Profile.tsx", "text-[15px]"): 1,
            ("src/screens/Profile.tsx", "text-blue-500"): 1,
            ("src/screens/Profile.tsx", "padding: 12"): 1,
            ("src/ui/Card.tsx", "p-[9px]"): 1,
        }
    )
    validate_whole_project(build(tmp_path, "web-fixed"))


def test_css_raw_values_red_then_fixed(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet with rules holds no typed value; one with only custom properties is a token file."""
    red = refusal(build(tmp_path, "css-red"))
    found = Counter(
        text for kind in ("colour", "size") for _, text in typed(red, kind).elements()
    )
    assert found == Counter(
        {
            "#123456": 1,
            "#1a2b3c": 1,
            "background: white": 1,
            "padding: 13px": 1,
            "width: 240px": 1,
            "height: 3rem": 1,
            "border-radius: 7px": 1,
            "font-size: 15px": 1,
        }
    )
    validate_whole_project(build(tmp_path, "css-fixed"))


def test_plain_html_red_then_fixed(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a plain HTML page holds no base element or typed value; its controls come from the ui folder."""
    red = refusal(build(tmp_path, "html-red"))
    found = Counter(
        (name.split(":")[0], tag)
        for name, tag in hits(red, "a base element").elements()
    )
    assert found == Counter(
        {
            ("src/index.html", "<button"): 1,
            ("src/app.js", "createElement('input')"): 1,
        }
    )
    assert typed(red, "size") == Counter({("src/index.html:6", "padding: 13px"): 1})
    validate_whole_project(build(tmp_path, "html-fixed"))


def test_unchanged_old_lines_are_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: old raw lines in a file the change leaves alone fail the full check; the quick check reads added lines only."""
    root = build(tmp_path, "web-red")
    base = commit(root, "base")
    (root / "src/screens/Other.tsx").write_text("export const Other = () => null;\n")
    commit(root, "change")
    validate_rules(root, base)
    message = refusal(root)
    assert "src/screens/Login.tsx:7: a base element (<button)" in message
    assert (
        "src/screens/Profile.tsx:4: a colour typed in the file (bg-[#1a2b3c])"
        in message
    )
    with pytest.raises(ValueError, match="HE-UI-SOURCE"):
        validate_rules(root, base, full=True)


def test_style_object_with_several_properties_counts_each_value_once(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a value belongs to its own property, so one object on one line gives one finding per typed value."""
    root = build(tmp_path, "web-fixed")
    (root / "src/screens/Inline.tsx").write_text(
        'export const A = () => <p style={{ fontSize: "1.2rem", fontWeight: 600, marginTop: 8 }} />;\n'
        "export const B = () => <p style={{ padding: 4, margin: 2 }} />;\n"
    )
    found = typed(refusal(root), "size")
    assert found == Counter(
        {
            ("src/screens/Inline.tsx:1", "font-size: 1.2rem"): 1,
            ("src/screens/Inline.tsx:1", "margin-top: 8"): 1,
            ("src/screens/Inline.tsx:2", "padding: 4"): 1,
            ("src/screens/Inline.tsx:2", "margin: 2"): 1,
        }
    )


def test_markup_styles_and_mixed_stylesheet_theme_names(tmp_path: Path) -> None:
    """HE-UI-SOURCE: an inline style beside a template brace is judged; a palette name that a stylesheet's theme block defines is not a default class."""
    root = build(tmp_path, "web-fixed")
    (root / "src/inline.vue").write_text(
        '<p style="padding: 13px">{{ name }}</p>\n'
        '<p class="text-gray-600 text-red-500">x</p>\n'
    )
    (root / "src/styles").mkdir()
    (root / "src/styles/app.css").write_text(
        "@theme {\n  --color-gray-600: #475569;\n}\n.card {\n  margin: var(--spacing-3);\n}\n"
    )
    message = refusal(root)
    assert typed(message, "size") == Counter({("src/inline.vue:1", "padding: 13px"): 1})
    assert typed(message, "colour") == Counter(
        {
            ("src/inline.vue:2", "text-red-500"): 1,
            ("src/styles/app.css:2", "#475569"): 1,
        }
    )


def test_default_palette_finding_names_the_fix(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a default palette class is a finding whose text says to define the project's own colours and clear the defaults."""
    message = refusal(build(tmp_path, "web-red"))
    line = next(row for row in message.splitlines() if "(text-blue-500)" in row)
    assert "--color-*: initial" in line


def library_message(tmp_path: Path, ui_library: list[str]) -> str:
    return refusal(build(tmp_path, "web-fixed", ui_library=ui_library))


def test_ui_library_setting_is_required_with_ui_paths(tmp_path: Path) -> None:
    """HE-UI-SOURCE: ui_paths needs a ui_library that lies inside it and matches a file; an old policy without the key still loads."""
    assert "ui_library is missing or empty" in library_message(
        tmp_path / "a", ui_library=[]
    )
    assert "ui_library entry src/none/* matches no file" in library_message(
        tmp_path / "b", ui_library=["src/none/*"]
    )
    root = build(tmp_path / "c", "web-fixed", ui_library=["src/ui/*", "docs/*"])
    (root / "docs").mkdir()
    (root / "docs/notes.txt").write_text("notes\n")
    outside = refusal(root)
    assert "ui_library entry docs/* is outside ui_paths" in outside
    validate_whole_project(build(tmp_path / "d", "web-fixed"))
    root = build(tmp_path / "e", "web-fixed")
    policy = json.loads((root / "hard-eng.gates.json").read_text())
    del policy["shipping"]["ui_library"]
    (root / "hard-eng.gates.json").write_text(json.dumps(policy))
    loaded = shipping.load_policy(root)
    assert loaded is not None
    assert loaded["ui_library"] == []


def test_library_that_holds_every_ui_file_is_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a ui_library equal to ui_paths hides every screen from the base element rule, so a screen must lie outside it."""
    message = refusal(build(tmp_path, "web-red", ui_library=["src/**"]))
    assert "ui_library holds every UI file of ui_paths" in message
    assert "ui_library holds every UI file" not in refusal(
        build(tmp_path / "ok", "web-red")
    )


def test_no_exemption_setting_exists(tmp_path: Path) -> None:
    """HE-UI-SOURCE: the policy has no exemption setting, so a key such as ui_ignore is refused as unknown."""
    for key in ("ui_ignore", "ui_exempt", "ui_waive"):
        root = build(tmp_path / key, "web-red")
        gates = json.loads((root / "hard-eng.gates.json").read_text())
        gates["shipping"][key] = ["src/screens/*"]
        (root / "hard-eng.gates.json").write_text(json.dumps(gates))
        with pytest.raises(shipping.ShippingError, match="unknown or missing keys"):
            shipping.load_policy(root)
    shipped = set(shipping._OPTIONAL_KEYS) | set(shipping._CONFIG_KEYS)
    assert not [key for key in shipped if re.search(r"ignore|exempt|waive|skip", key)]


def full_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, ".hooks/hard-eng.py", "check", "--only-language", "swift"]
        + ["--plan-stage", "Complete"],
        cwd=root,
        env={**os.environ, "CI": "true"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_raw_button_to_library_journey_end_to_end(
    tmp_path: Path, completed_plan: str
) -> None:
    """HE-UI-SOURCE: in a sealed copy the real full check refuses a screen with a raw button and a hex colour, and passes once the button is a library part, the colour a token and the index written."""
    root = build(tmp_path, "web-fixed")
    shutil.copytree(
        Path(__file__).parents[1] / ".hooks",
        root / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    gates = json.loads((root / "hard-eng.gates.json").read_text())
    (root / "hard-eng.gates.json").write_text(
        json.dumps(
            gates
            | {
                "packages": [],
                "shared": [gate("ok", "pass", role="custom", parallel=True)],
            }
        )
    )
    (root / "PRODUCT.md").write_text(
        (Path(__file__).parents[1] / "PRODUCT.md").read_text()
    )
    with (root / "DESIGN.md").open("a") as design:
        design.write(
            "\n## Overview\n\nA fixture design.\n\n## Components\n\nButton and Modal.\n"
            "\n## Do's and Don'ts\n\nUse the tokens.\n"
        )
    commit(root, "base")
    (root / "PLAN.md").write_text(completed_plan)
    assert full_check(root).returncode == 0
    screen = root / "src/screens/Extra.tsx"
    screen.write_text(
        'export const Extra = () => <button style={{ color: "#0a0b0c" }}>Go</button>;\n'
    )
    refused = full_check(root)
    assert refused.returncode != 0
    assert (
        "a base element (<button) outside the library"
        in refused.stdout + refused.stderr
    )
    assert "a colour typed in the file (#0a0b0c)" in refused.stdout + refused.stderr
    (root / "src/ui/Action.tsx").write_text(
        'export const Action = () => <button className="text-accent">Go</button>;\n'
    )
    screen.write_text(
        'import { Action } from "../ui/Action";\nexport const Extra = () => <Action />;\n'
    )
    tokens = root / "src/theme/tokens.css"
    tokens.write_text(tokens.read_text().replace("}", "  --color-accent: #0a0b0c;\n}"))
    design = root / "DESIGN.md"
    design.write_text(
        design.read_text().replace("colors:\n", 'colors:\n  accent: "#0a0b0c"\n')
    )
    subprocess.run(
        [sys.executable, ".hooks/hard-eng.py", "ui-library", "--write"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    index = root / "UI-LIBRARY.md"
    index.write_text(
        index.read_text().replace("- `Action` — ", "- `Action` — a plain action")
    )
    passed = full_check(root)
    assert passed.returncode == 0, passed.stdout + passed.stderr


def test_empty_ui_paths_with_ui_files_is_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a project that lists no ui_paths but holds a component gets one line and no other UI finding."""
    root = build(tmp_path, "web-red", ui_paths=[], ui_library=[])
    message = refusal(root)
    assert message == "UI files found at src/screens/Login.tsx; add them to ui_paths."


def test_no_ui_project_skips_every_ui_check(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a backend project passes with no UI line, and no UI module is even imported."""
    root = tmp_path / "backend"
    init(root)
    files = {
        "README.md": "backend\n",
        "server/app.py": "print('x')\n",
        "server/routes.ts": "export const html = '<button>x</button>';\n",
        ".hooks/tool.js": "const a = '#123456';\n",
        "tests/page.html": "<button>fixture</button>\n",
        "generated/out.css": ".a { color: #123456; padding: 13px; }\n",
        ".gitattributes": "/generated/out.css linguist-generated\n",
        "hard-eng.gates.json": json.dumps(
            {"shipping": POLICY | {"ui_paths": [], "ui_library": []}}
        ),
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path\n"
        "from whole_project import validate_whole_project\n"
        "validate_whole_project(Path(sys.argv[2]))\n"
        "print(sorted({'ui_library', 'ui_tokens', 'ui_whole', 'ui_raw'} & set(sys.modules)))\n"
    )
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(Path(__file__).parents[1] / ".hooks"),
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


NO_UI_GUARD_FILES = {
    "src/App.js": "export const App = () => <div className='a'>x</div>;\n",
    "src/card.ts": 'import { html } from "lit";\nexport const t = html`<p>x</p>`;\n',
    "ios/Home.swift": "import SwiftUI\nstruct Home: View {}\n",
    "ios/Legacy.swift": "import UIKit\nclass Legacy: UIViewController {}\n",
    "android/Main.kt": "@Composable\nfun Home() {}\n",
    "android/app/src/main/res/layout/main.xml": "<LinearLayout/>\n",
    "app/lib/home.dart": "class Home extends StatelessWidget {}\n",
    "docs/index.html": "<p>docs</p>\n",
    "src/Mention.tsx": "// jspdf\nexport const A = () => <button>x</button>;\n",
}


@pytest.mark.parametrize("name", sorted(NO_UI_GUARD_FILES))
def test_no_ui_guard_counts_every_ui_stack(tmp_path: Path, name: str) -> None:
    """HE-UI-SOURCE: a project with empty ui_paths is refused for a file of any UI stack, not only web components."""
    root = tmp_path / "backend"
    init(root)
    files = {
        "README.md": "backend\n",
        "server/app.py": "print('x')\n",
        "hard-eng.gates.json": json.dumps(
            {"shipping": POLICY | {"ui_paths": [], "ui_library": []}}
        ),
        "app/pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n",
        name: NO_UI_GUARD_FILES[name],
    }
    for file, text in files.items():
        (root / file).parent.mkdir(parents=True, exist_ok=True)
        (root / file).write_text(text)
    assert refusal(root) == f"UI files found at {name}; add them to ui_paths."


@pytest.mark.parametrize(
    ("name", "text", "kind"),
    [
        ("a.ts", 'import { jsPDF } from "jspdf";\nnew jsPDF();\n', "pdf"),
        (
            "a.ts",
            "import {\n  PDFDocument,\n} from 'pdf-lib';\nPDFDocument.create();\n",
            "pdf",
        ),
        ("a.js", "const pdf = require('pdfmake/build/pdfmake');\npdf.run();\n", "pdf"),
        ("a.js", "const { jsPDF } = require('jspdf');\nnew jsPDF();\n", "pdf"),
        (
            "a.ts",
            "const m = await import('@react-pdf/renderer');\nm.render();\n",
            "pdf",
        ),
        ("a.ts", "import * as pdf from 'pdf-lib';\npdf.go();\n", "pdf"),
        ("a.ts", "import { type A, jsPDF as P } from 'jspdf';\nP();\n", "pdf"),
        (
            "a.tsx",
            "import { Button } from '@react-email/components';\n<Button />;\n",
            "email",
        ),
        ("a.ts", 'import mjml from "mjml";\nmjml(x);\n', "email"),
        ("a.dart", "import 'package:pdf/widgets.dart' as pw;\n", "pdf"),
        ("a.tsx", "// jspdf\nexport const A = () => <button />;\n", None),
        ("a.tsx", "// mjml\n<button />\n", None),
        ("a.tsx", "// import x from 'jspdf';\n", None),
        ("a.tsx", "/* require('pdf-lib') */\n", None),
        ("a.tsx", "run(); // require('jspdf')\n", None),
        ("a.css", "/* pdf-lib */\n.a { color: red; }\n", None),
        ("a.css", '@import "jspdf";\n', None),
        ("a.html", "<script>import x from 'jspdf'</script>\n", None),
        ("a.dart", "// import 'package:pdf/pdf.dart';\n", None),
        ("a.tsx", "const s = \"import x from 'jspdf'\";\nx;\n", None),
        ("a.tsx", "const s = `import x from 'jspdf'`;\nx;\n", None),
        ("a.tsx", "const a = <code>import x from 'jspdf'</code>;\nx;\n", None),
        ("a.tsx", "const s = \"import m from 'mjml'\";\nm;\n", None),
        ("a.ts", "import 'jspdf';\n", None),
        ("a.ts", "import 'mjml';\n", None),
        ("a.ts", "import type { jsPDF } from 'jspdf';\nlet a: jsPDF;\n", None),
        ("a.ts", "import { jsPDF } from 'jspdf';\n", None),
        ("a.ts", "if (false) import('jspdf');\n", None),
        ("a.ts", "const m = await import('jspdf');\n", None),
        ("a.ts", "export * from 'jspdf';\n", None),
    ],
)
def test_exemption_reads_real_import_forms_only(
    name: str, text: str, kind: str | None
) -> None:
    """HE-UI-SOURCE: a PDF or email library named in a comment, a stylesheet or HTML exempts nothing; only an import of it does."""
    assert exemption(name, text) == kind


def test_no_ui_guard_passes_files_the_exemption_reader_exempts(tmp_path: Path) -> None:
    """HE-UI-SOURCE: email templates, standalone pages and PDF code do not make a backend a UI project; a docs page does."""
    root = tmp_path / "backend"
    init(root)
    files = {
        "README.md": "backend\n",
        "server/app.py": "print('x')\n",
        "hard-eng.gates.json": json.dumps(
            {"shipping": POLICY | {"ui_paths": [], "ui_library": []}}
        ),
        "emails/welcome.html": "<p>hi</p>\n",
        "server/page.ts": "export const p = `<!doctype html><p>x</p>`;\n",
        "server/pdf.tsx": 'import { Document } from "@react-pdf/renderer";\nexport const P = () => <Document>x</Document>;\n',
        "server/mail.tsx": 'import { Button } from "@react-email/components";\nexport const M = () => <Button>x</Button>;\n',
        "server/routes.ts": "export const html = '<button>x</button>';\n",
    }
    for file, text in files.items():
        (root / file).parent.mkdir(parents=True, exist_ok=True)
        (root / file).write_text(text)
    validate_whole_project(root)
    (root / "docs").mkdir()
    (root / "docs/index.html").write_text("<p>docs</p>\n")
    assert refusal(root) == "UI files found at docs/index.html; add them to ui_paths."


def flutter_app(root: Path) -> None:
    (root / "app/lib").mkdir(parents=True)
    (root / "app/pubspec.yaml").write_text(
        "dependencies:\n  flutter:\n    sdk: flutter\n"
    )
    policy = json.loads((root / "hard-eng.gates.json").read_text())
    policy["packages"] = [{"name": "app", "path": "app", "language": "dart"}]
    (root / "hard-eng.gates.json").write_text(json.dumps(policy))


def test_component_files_outside_ui_paths_are_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a component file that ui_paths misses is refused, so a wrong ui_paths hides no screen."""
    root = build(tmp_path, "web-fixed", ui_paths=["src/screens/**", "src/ui/**"])
    (root / "src/other").mkdir()
    (root / "src/other/Hidden.tsx").write_text("export const Hidden = () => null;\n")
    (root / "src/other/Hidden.test.tsx").write_text("export const T = () => null;\n")
    flutter_app(root)
    (root / "app/lib/screen.dart").write_text("class Home extends StatelessWidget {}\n")
    (root / "app/lib/logic.dart").write_text("int add(int a, int b) => a + b;\n")
    message = refusal(root)
    assert "src/other/Hidden.tsx: a component file outside ui_paths" in message
    assert "app/lib/screen.dart: a component file outside ui_paths" in message
    assert "logic.dart" not in message
    assert "Hidden.test.tsx" not in message


def test_only_a_widget_class_makes_a_dart_file_a_component(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a Dart file that names WidgetsFlutterBinding but holds no Widget is no component, in the coverage rule and in the no-UI guard."""
    binding = "void main() {\n  WidgetsFlutterBinding.ensureInitialized();\n}\n"
    root = build(tmp_path / "cov", "web-fixed")
    flutter_app(root)
    (root / "app/lib/main.dart").write_text(binding)
    validate_whole_project(root)
    guard = tmp_path / "guard"
    init(guard)
    files = {
        "README.md": "backend\n",
        "app/pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n",
        "app/lib/main.dart": binding,
        "hard-eng.gates.json": json.dumps(
            {"shipping": POLICY | {"ui_paths": [], "ui_library": []}}
        ),
    }
    for file, text in files.items():
        (guard / file).parent.mkdir(parents=True, exist_ok=True)
        (guard / file).write_text(text)
    validate_whole_project(guard)
    (guard / "app/lib/home.dart").write_text("class H extends StatelessWidget {}\n")
    assert (
        refusal(guard) == "UI files found at app/lib/home.dart; add them to ui_paths."
    )


def test_a_pdf_widget_file_outside_ui_paths_is_not_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: coverage follows the PDF exemption, so a PDF builder widget outside ui_paths gets no line while another widget does."""
    root = build(tmp_path, "web-fixed")
    flutter_app(root)
    (root / "app/lib/page.dart").write_text(
        "import 'package:pdf/widgets.dart' as pw;\nclass P extends pw.StatelessWidget {}\n"
    )
    (root / "app/lib/screen.dart").write_text("class S extends StatelessWidget {}\n")
    message = refusal(root)
    assert "app/lib/screen.dart: a component file outside ui_paths" in message
    assert "page.dart" not in message


def test_one_library_part_per_fixed_control(tmp_path: Path) -> None:
    """HE-UI-SOURCE: each fixed control has one library part; two parts that share a role word fail, one each passes."""
    root = build(tmp_path, "web-fixed")
    (root / "src/ui/Empty.tsx").write_text(
        "export function EmptyState() {\n  return null;\n}\n"
        "export const PasswordField = () => null;\n"
    )
    reindex(root)
    validate_whole_project(root)
    (root / "src/ui/Tiles.tsx").write_text(
        "export function TileEmptyState() {\n  return null;\n}\n"
        "export class FieldError {}\n"
        "export const ErrorMessage = () => null;\n"
    )
    message = refusal(root)
    assert "empty state: 2 library parts (EmptyState, TileEmptyState)" in message
    assert "error message: 2 library parts (ErrorMessage, FieldError)" in message
    assert "password field" not in message


def test_library_index_is_generated_and_compared(tmp_path: Path) -> None:
    """HE-UI-SOURCE: UI-LIBRARY.md lists each library part; a missing file, part or use line and a stale row fail; --write keeps use lines."""
    root = build(tmp_path, "web-fixed", index=False)
    assert "UI-LIBRARY.md is missing" in refusal(root)

    def write() -> None:
        subprocess.run(
            [sys.executable, ".hooks/hard-eng.py", "ui-library", "--write"],
            cwd=root,
            check=True,
            capture_output=True,
        )

    shutil.copytree(
        Path(__file__).parents[1] / ".hooks",
        root / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    write()
    index = root / "UI-LIBRARY.md"
    assert "- `Button` — \n" in index.read_text()
    assert "src/ui/Button.tsx:" not in index.read_text()
    assert "use line of Button is empty" in refusal(root)
    filled = index.read_text().replace("- `Button` — ", "- `Button` — a plain button")
    index.write_text(filled.replace("- `Modal` — ", "- `Modal` — a dialog"))
    validate_whole_project(root)
    (root / "src/ui/Extra.tsx").write_text("export const Extra = () => null;\n")
    assert "Extra is missing from UI-LIBRARY.md" in refusal(root)
    write()
    assert "- `Button` — a plain button" in index.read_text()
    assert "- `Extra` — \n" in index.read_text()
    (root / "src/ui/Extra.tsx").unlink()
    assert "UI-LIBRARY.md lists Extra, which no library file holds" in refusal(root)


def test_a_comment_a_test_file_and_a_generated_file_define_no_token(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a colour that only a comment, a test file or a generated file defines is no project token, so a default palette class and an email literal that use it stay refused."""
    root = build(
        tmp_path, "web-fixed", ui_paths=["src/**", "emails/**"], ui_library=["src/ui/*"]
    )
    (root / "src/screens/Card.tsx").write_text(
        'export const Card = () => <p className="text-blue-500">x</p>;\n'
    )
    (root / "emails").mkdir()
    (root / "emails/welcome.html").write_text('<p style="color: #3b82f6">x</p>\n')
    reindex(root)
    assert "(text-blue-500)" in refusal(root)
    with (root / "src/theme/tokens.css").open("a") as tokens:
        tokens.write("/* @theme { --color-blue-500: #3b82f6; } */\n")
    message = refusal(root)
    assert "(text-blue-500)" in message
    assert "emails/welcome.html:1: a colour typed in the file (#3b82f6)" in message
    (root / "tests/fixtures").mkdir(parents=True)
    (root / "tests/fixtures/theme.css").write_text(
        "@theme {\n  --color-blue-500: #3b82f6;\n}\n"
    )
    (root / "src/generated.css").write_text("@theme {\n  --color-blue-500: #3b82f6;\n}\n")
    (root / ".gitattributes").write_text("src/generated.css linguist-generated\n")
    message = refusal(root)
    assert "(text-blue-500)" in message
    assert "emails/welcome.html:1: a colour typed in the file (#3b82f6)" in message


def test_the_library_index_and_the_token_compare_skip_tests_and_generated_files(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a test file or a generated file in the library folder needs no row in UI-LIBRARY.md, and a test fixture's tailwind config is not compared with DESIGN.md."""
    root = build(tmp_path, "web-fixed")
    (root / "src/ui/Button.test.tsx").write_text(
        "export const FakeButton = () => null;\n"
    )
    (root / "src/ui/Wrapper.tsx").write_text("export const Wrapper = () => null;\n")
    (root / ".gitattributes").write_text("src/ui/Wrapper.tsx linguist-generated\n")
    (root / "tests/fixtures").mkdir(parents=True)
    (root / "tests/fixtures/tailwind.config.js").write_text(
        "module.exports = { theme: { colors: { brand: '#abcdef' } } };\n"
    )
    validate_whole_project(root)
    for name in ("src/ui/Button.test.tsx", "src/ui/Wrapper.tsx"):
        (root / name).write_text(
            (root / name).read_text() + "export const Extra = () => null;\n"
        )
    validate_whole_project(root)


def test_a_mixed_stylesheet_gets_a_token_gap_line_that_says_why(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet that holds @theme tokens and other rules is no token file; the finding says why and what passes, and moving the tokens to a stylesheet of custom properties only passes."""
    root = build(tmp_path, "web-fixed")
    (root / "src/theme/tokens.css").unlink()
    (root / "src/styles").mkdir()
    (root / "src/styles/globals.css").write_text(
        "@theme {\n  --color-brand: #123456;\n  --spacing-3: 12px;\n}\n"
        ".card {\n  margin: var(--spacing-3);\n}\n"
    )
    (root / "DESIGN.md").write_text(
        "---\ncolors:\n  brand: '#123456'\nspacing:\n  s3: 12px\n---\n# Fixture\n"
    )
    message = refusal(root)
    assert "the DESIGN.md colour #123456 is missing from the token files" in message
    assert (
        "src/styles/globals.css holds @theme tokens and other rules, so it is not a token file"
        in message
    )
    assert "move the tokens to a stylesheet of custom properties only" in message
    (root / "src/styles/globals.css").write_text(
        ".card {\n  margin: var(--spacing-3);\n}\n"
    )
    (root / "src/theme/tokens.css").write_text(
        "@theme {\n  --color-brand: #123456;\n  --spacing-3: 12px;\n}\n"
    )
    reindex(root)
    validate_whole_project(root)


def test_exemptions_follow_repository_facts(tmp_path: Path) -> None:
    """HE-UI-SOURCE: email templates, standalone pages and PDF builders are judged by what the repository says they are, never by a path list."""
    root = build(
        tmp_path,
        "web-fixed",
        ui_paths=["src/**", "emails/**"],
        ui_library=["src/ui/*"],
    )
    (root / "src/theme/tokens.css").write_text(
        "@theme {\n  --color-brand: #123456;\n  --spacing-3: 12px;\n}\n"
    )
    good = '<button style="color: #123456; padding: 12px">Go</button>\n'
    (root / "emails").mkdir()
    (root / "emails/welcome.html").write_text(good)
    (root / "src/mail.tsx").write_text(
        'import { Button } from "@react-email/components";\n'
        'export const M = () => <Button style={{ color: "#123456" }}>x</Button>;\n'
    )
    (root / "src/page.ts").write_text(
        'export const page = `<!doctype html><p style="color: #123456; padding: 12px">x</p>`;\n'
    )
    (root / "src/pdf.tsx").write_text(
        'import { Document } from "@react-pdf/renderer";\n'
        "export const P = () => <Document style={{ padding: 13 }}>x</Document>;\n"
    )
    (root / "src/gen.css").write_text(".a { color: #999999; }\n")
    (root / ".gitattributes").write_text("src/gen.css linguist-generated\n")
    reindex(root)
    validate_whole_project(root)
    (root / "emails/welcome.html").write_text(good.replace("#123456", "#999999"))
    (root / "src/page.ts").write_text(
        'export const page = `<!doctype html><button>x</button><p style="color: #123456">x</p>`;\n'
    )
    message = refusal(root)
    assert "emails/welcome.html:1: a colour typed in the file (#999999)" in message
    assert "src/page.ts:1: a base element (<button)" in message
    assert message.count("typed in the file") == 1
    assert "mail.tsx" not in message
    assert "pdf.tsx" not in message


def design_root(tmp_path: Path, fixture: str, **changes: object) -> Path:
    root = tmp_path / fixture
    init(root)
    shutil.copytree(FIXTURES / fixture, root, dirs_exist_ok=True)
    policy = {
        "ui_paths": ["src/**", "lib/**"],
        "ui_library": ["src/theme/*"],
    } | changes
    (root / "hard-eng.gates.json").write_text(json.dumps({"shipping": POLICY | policy}))
    (root / "README.md").write_text("fixture, parts in UI-LIBRARY.md\n")
    (root / "UI-LIBRARY.md").write_text("## `src/theme/*`\n\n")
    return root


def test_design_md_and_tokens_match(tmp_path: Path) -> None:
    """HE-UI-SOURCE: DESIGN.md front matter and the token files hold the same colours, lengths and font families; any DESIGN.md values pass when they match."""
    validate_whole_project(design_root(tmp_path, "tokens-fixed"))
    root = design_root(tmp_path, "tokens-red")
    message = refusal(root)
    for line in (
        "a token colour #123457 is missing from DESIGN.md",
        "a token colour #0a0b0c is missing from DESIGN.md",
        "the DESIGN.md colour #777777 is missing from the token files",
        "the DESIGN.md length 22px is missing from the token files",
        "a token length 768px is missing from DESIGN.md",
        "a token length 7px is missing from DESIGN.md",
        "the DESIGN.md font family Georgia is missing from the token files",
        "the token brand is #123457 but DESIGN.md says #123456",
    ):
        assert line in message, line
    assert "0.5" not in message
    (root / "DESIGN.md").write_text("# Design\n")
    assert "DESIGN.md has no front matter" in refusal(root)
    (root / "DESIGN.md").unlink()
    assert "DESIGN.md is missing" in refusal(root)


FLUTTER_UI = ["app/lib/core/**", "app/lib/ui/**", "app/lib/screens/**", "app/ios/**"]


def flutter_root(tmp_path: Path, fixture: str) -> Path:
    root = tmp_path / fixture
    init(root)
    shutil.copytree(FIXTURES / fixture, root, dirs_exist_ok=True)
    policy = {
        "shipping": POLICY | {"ui_paths": FLUTTER_UI, "ui_library": ["app/lib/ui/*"]},
        "packages": [{"name": "app", "path": "app", "language": "dart"}],
    }
    (root / "hard-eng.gates.json").write_text(json.dumps(policy))
    (root / "README.md").write_text("fixture, parts in UI-LIBRARY.md\n")
    texts = text_files(root)
    library = ["app/lib/ui/*"]
    uses = {
        entry: dict.fromkeys(parts, "a part")
        for entry, parts in expected_index(texts, library).items()
    }
    (root / "UI-LIBRARY.md").write_text(index_text(texts, library, uses))
    return root


def test_flutter_red_then_fixed(tmp_path: Path) -> None:
    """HE-UI-SOURCE: Dart and Swift colours typed in a screen, a token colour DESIGN.md lacks, two empty states, a widget file outside ui_paths and a stale index are each refused; the fixed project passes."""
    validate_whole_project(flutter_root(tmp_path, "flutter-fixed"))
    root = flutter_root(tmp_path, "flutter-red")
    with (root / "UI-LIBRARY.md").open("a") as index:
        index.write("- `Ghost` — gone\n")
    message = refusal(root)
    assert typed(message, "colour") == Counter(
        {
            ("app/lib/screens/home.dart:2", "Color(0x"): 1,
            ("app/ios/Runner/Banner.swift:4", "Color(red:"): 1,
        }
    )
    for line in (
        "a token colour #abcdef is missing from DESIGN.md",
        "empty state: 2 library parts (EmptyState, TileEmptyState)",
        "app/lib/other/hidden.dart: a component file outside ui_paths",
        "UI-LIBRARY.md lists Ghost, which no library file holds",
    ):
        assert line in message, line


def test_style_sheets_outside_ui_paths_are_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet that ui_paths misses is refused like a component file, so raw values cannot hide there."""
    root = build(tmp_path, "web-fixed")
    (root / "styles").mkdir()
    for suffix in ("css", "scss", "less"):
        (root / f"styles/app.{suffix}").write_text(".a { color: #999999; }\n")
    message = refusal(root)
    for suffix in ("css", "scss", "less"):
        assert f"styles/app.{suffix}: a stylesheet outside ui_paths" in message


def test_only_style_and_script_files_are_token_files(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a component in a theme folder is judged like any screen, and script token files join the token compare."""
    assert not token_file("src/theme/Card.tsx", "")
    for name in ("Card.jsx", "Card.vue", "Card.svelte", "Card.astro", "card.html"):
        assert not token_file(f"src/tokens/{name}", "")
    assert token_file("src/theme/colors.ts", "")
    root = design_root(tmp_path, "tokens-fixed")
    (root / "src/theme/Card.tsx").write_text(
        'export const Card = () => <p className="p-[13px]">x</p>;\n'
    )
    assert "src/theme/Card.tsx:1: a size typed in the file (p-[13px])" in refusal(root)
    (root / "src/theme/Card.tsx").unlink()
    (root / "src/theme/colors.ts").write_text('export const extra = "#0f0f0f";\n')
    (root / "tailwind.config.js").write_text('module.exports = { brand: "#fedcba" };\n')
    message = refusal(root)
    assert "a token colour #0f0f0f is missing from DESIGN.md" in message
    assert "a token colour #fedcba is missing from DESIGN.md" in message


def front(data: dict[str, object]) -> str:
    return f"---\n{yaml.safe_dump(data)}---\n"


def test_token_readers_cover_real_token_forms() -> None:
    """HE-UI-SOURCE: the compare reads any family custom property, line heights, nested lengths and Dart Colors names, and leaves shadows as text."""
    design = front(
        {
            "colors": {"brand": "#2196f3"},
            "typography": {
                "body": {
                    "fontFamily": "Inter",
                    "fontSize": "16px",
                    "lineHeight": "28px",
                    "letterSpacing": "2px",
                }
            },
            "components": {"button": {"height": "52px", "padding": {"x": "8px"}}},
            "spacing": {"s": "8px"},
        }
    )
    css = (
        '@theme {\n  --type-family: "Inter", sans-serif;\n  --size-body: 16px;\n'
        "  --leading: 28px;\n  --tracking: 2px;\n  --height-button: 52px;\n"
        "  --space-s: 8px;\n"
        "  --shadow-card: 0 4px 18px rgba(1, 2, 3, 0.2);\n}\n"
    )
    dart = "static const brand = Colors.blue;\n"
    assert token_findings(design, [css, dart]) == []
    assert token_findings(design, ["--other-family: Georgia, serif;\n"]) != []


def test_dart_string_constants_are_font_families_and_letter_spacing_is_a_length() -> (
    None
):
    """HE-UI-SOURCE: static const String family names and letter spacing in Dart match DESIGN.md; other doubles below 1 are not lengths."""
    design = front(
        {
            "typography": {
                "body": {"fontFamily": "Urbanist", "letterSpacing": "0.5px"},
                "caps": {"fontFamily": "Inter", "letterSpacing": "1.5px"},
            }
        }
    )
    dart = (
        "class T {\n  static const String fontFamily = 'Urbanist';\n"
        "  static const String family = 'Inter';\n"
        "  static const style = TextStyle(letterSpacing: 0.5);\n"
        "  static const double letterSpacing = 1.5;\n"
        "  static const double fade = 0.3;\n}\n"
    )
    assert token_findings(design, [dart]) == []
    missing = token_findings(design, ["static const double letterSpacing = 2;\n"])
    assert "a token length 2px is missing from DESIGN.md" in missing
    assert "the DESIGN.md length 0.5px is missing from the token files" in missing


def test_a_font_property_that_is_not_a_family_adds_no_family() -> None:
    """HE-UI-SOURCE: --font-size, --font-weight, --font-style and --font-tracking values are no font family, so DESIGN.md need not list `.875rem` or `bold`; a family property still is one."""
    css = (
        "@theme {\n  --font-size-sm: .875rem;\n  --font-size-body: clamp(1rem, 2vw, 1.25rem);\n"
        "  --font-weight-bold: bold;\n  --font-style-italic: italic;\n"
        "  --font-tracking-tight: -0.02em;\n"
        '  --font-sans: "Inter", sans-serif;\n  --type-family: Georgia, serif;\n}\n'
    )
    assert token_facts([css]).families == {"Inter", "Georgia"}
    assert token_facts(["--font-display: Lora;\n"]).families == {"Lora"}


def test_a_letter_spacing_product_is_no_literal_length() -> None:
    """HE-UI-SOURCE: letterSpacing: 12.5 * 0.02 is an expression, not the length 12.5; a plain literal in a call is read."""
    assert token_facts(["TextStyle(letterSpacing: 12.5 * 0.02)\n"]).lengths == set()
    assert token_facts(["TextStyle(letterSpacing: 0.5)\n"]).lengths == {0.5}
    assert token_facts(["TextStyle(letterSpacing: 1.5, fontSize: 12)\n"]).lengths == {
        1.5,
        12.0,
    }


def test_a_length_message_prints_the_typed_text_and_its_px_value() -> None:
    """HE-UI-SOURCE: a rem or em length is named as written with the px value after it, so a fixer can search for it; a px length stays plain."""
    design = front({"colors": {"brand": "#2196f3"}, "spacing": {"a": "0.5rem"}})
    found = token_findings(design, ["--x: 0.08em;\n--y: 12px;\n"])
    assert "a token length 0.08em (1.28px) is missing from DESIGN.md" in found
    assert "a token length 12px is missing from DESIGN.md" in found
    assert "the DESIGN.md length 0.5rem (8px) is missing from the token files" in found


def test_comments_in_token_files_are_not_tokens() -> None:
    """HE-UI-SOURCE: a length, colour or family named in a doc comment, a line comment or a block comment is no token; a // comment that holds /* hides nothing after it."""
    text = (
        "/// 1pt of spacing\n/* 0.6em and #123456 */\n// 16pt\n"
        "static const double space = 12;\n"
    )
    facts = token_facts([text])
    assert facts.lengths == {12.0}
    assert facts.colours == set()
    opener = "// see /* here\nstatic const double a = 12;\nstatic const double b = 13; // */\n"
    assert token_facts([opener]).lengths == {12.0, 13.0}
    assert token_facts(["--a: 1px; /* x */ --b: 2px; // 3px\n"]).lengths == {1.0, 2.0}


def test_dart_shadow_colours_stay_text() -> None:
    """HE-UI-SOURCE: a Dart colour given to a shadow argument is not a token colour that DESIGN.md must list."""
    design = front({"colors": {"brand": "#2196f3"}})
    dart = "static const brand = Colors.blue;\nfinal scheme = ColorScheme(shadow: Colors.black, shadowColor: Colors.red);\n"
    assert token_findings(design, [dart]) == []


def test_native_rule_reads_the_forms_the_token_reader_reads_and_named_system_colours() -> (
    None
):
    """HE-UI-SOURCE: Color.new(0x...), Color(0X...), Swift Color.red and a named colour in a colour modifier are raw colours; asset and semantic colours are not."""

    def flagged(name: str, line: str) -> bool:
        return bool(native_findings(name, [(1, line)]))

    for dart in ("final a = Color.new(0xFF000000);", "final a = Color(0XFF000000);"):
        assert flagged("lib/a.dart", dart), dart
    for swift in (
        'Text("x").foregroundColor(.red)',
        "let c = Color.red",
        "let c = UIColor.blue",
        "Circle().fill(.green)",
        "view.backgroundColor = UIColor.white",
    ):
        assert flagged("ios/A.swift", swift), swift
    for swift in (
        'Text("x").foregroundColor(Color("brand"))',
        "Text(x).foregroundColor(.primary)",
        "let c = Color.primary",
        "let redCount = items.red",
    ):
        assert not flagged("ios/A.swift", swift), swift
    assert not flagged("lib/a.dart", "final a = Color(brand);")


def test_dart_colour_findings_name_the_whole_colour() -> None:
    """HE-UI-SOURCE: the finding names Colors.red, not its first letter."""
    found = native_findings(
        "lib/a.dart", [(1, "  c: cond ? Colors.red : Colors.green,")]
    )
    assert len(found) == 1
    assert found[0].startswith(
        "lib/a.dart:1: a colour typed in the file (Colors.red). "
    )


def test_bad_design_front_matter_is_a_finding_not_a_traceback() -> None:
    """HE-UI-SOURCE: DESIGN.md front matter that is not YAML gives a finding."""
    found = token_findings("---\ncolors: [unclosed\n---\n", [])
    assert found
    assert "DESIGN.md front matter is not valid YAML" in found[0]


def test_generic_dart_widget_is_listed_in_library_parts() -> None:
    """HE-UI-SOURCE: generic Dart widget classes such as DropdownField<T> count as library parts."""
    texts = {
        "lib/core/widgets/dropdown.dart": (
            "class AppDropdownField<T> extends StatelessWidget {}\n"
            "class AppButton extends ConsumerWidget {}\n"
        )
    }
    assert expected_index(texts, ["lib/core/widgets/**"]) == {
        "lib/core/widgets/**": ["AppButton", "AppDropdownField"]
    }


def test_canonical_flutter_profile_names_the_lint_release(
    tmp_path: Path, installer: ModuleType
) -> None:
    """HE-UI-SOURCE: canonical Flutter profile pins flutter_skill_lints ^0.16.0 and setup raises older pins to it."""
    profile = (
        Path(__file__).parents[1]
        / ".agents/skills/building-flutter-apps/references/analysis_options.yaml"
    )
    pin = yaml.safe_load(profile.read_text())["plugins"]["flutter_skill_lints"]
    assert pin == "^0.16.0"
    package = tmp_path / "app"
    (package / "lib").mkdir(parents=True)
    (package / "pubspec.yaml").write_text(
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    (package / "analysis_options.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.15.0"}})
    )
    changes: dict[str, str] = {}
    installer.configure_dart(
        tmp_path, package, {"path": "app", "sources": ["lib"], "checks": []}, changes
    )
    updated = yaml.safe_load(changes["app/analysis_options.yaml"])
    assert updated["plugins"]["flutter_skill_lints"] == "^0.16.0"
