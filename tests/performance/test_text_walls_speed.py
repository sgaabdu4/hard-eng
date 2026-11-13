"""HE-NO-TEXT-WALLS: reading a thousand screen files costs under one second of processor time."""

import resource
from pathlib import Path

import text_walls
from conftest import init

SCREEN = """import { useState } from "react";

export function Panel({ user, items }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section className="panel">
      <h2 title="Account summary">Hello {user.name}, welcome back.</h2>
      <p>
        Your plan renews on <strong>{user.renews}</strong>. Manage it any time.
      </p>
      <ul>
        {items.map((item) => (
          <li key={item.id}>{item.label}</li>
        ))}
      </ul>
      <button onClick={() => setOpen(!open)}>Show details</button>
    </section>
  );
}
"""


def used() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime


def test_one_thousand_screen_files_take_under_one_second_of_cpu(
    tmp_path: Path,
) -> None:
    """HE-NO-TEXT-WALLS: the whole list path, from the file list to the verdict, for 1,000 screens."""
    root = tmp_path / "repo"
    init(root)
    (root / "src").mkdir()
    for number in range(1000):
        (root / f"src/Panel{number}.tsx").write_text(SCREEN)
    caps = text_walls.settings(root)
    assert text_walls.listed_walls(root, ["src/Panel0.tsx"], caps) == []
    before = used()
    assert text_walls.listed_walls(root, [], caps) == []
    assert used() - before < 1.0
