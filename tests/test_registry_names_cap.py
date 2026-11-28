"""CLI text, CLI JSON and `archy_brief` show the same number of registry names (#614)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archy.cli_render_conventions import _conventions_to_dict, _conventions_to_text
from archy.conventions import compute_conventions
from archy.conventions_models import REGISTRY_LITERAL_NAMES_SHOWN
from archy.mcp_runs import run_brief

DECLARED = [f"name-{i:02d}" for i in range(9)]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    declarations = "".join(f'C{i} = Code("{name}")\n' for i, name in enumerate(DECLARED))
    (tmp_path / "pkg" / "codes.py").write_text(
        "class Code:\n    def __init__(self, name): pass\n" + declarations, encoding="utf-8"
    )
    return tmp_path


def test_every_surface_cuts_at_the_same_number(project: Path):
    report = compute_conventions(project)
    # The fixture declares more names than are shown, or nothing is being cut.
    assert len(report.registries[0].literal_names) == len(DECLARED) > 6
    assert REGISTRY_LITERAL_NAMES_SHOWN == 6

    cli_json = _conventions_to_dict(report, top_n=8)["registries"][0]["literal_names"]
    brief = run_brief(project, top_n=8, with_contracts=False, include_tests=False)
    mcp = brief.model_dump()["conventions"]["registries"][0]["literal_names"]
    text = _conventions_to_text(report, top_n=8)

    assert list(cli_json) == list(mcp) == DECLARED[:6]
    assert f"{', '.join(DECLARED[:6])} (+3)" in text
    assert DECLARED[6] not in text


def test_nothing_is_said_to_be_hidden_when_all_fit(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "codes.py").write_text(
        "class Code:\n    def __init__(self, name): pass\n"
        + "".join(f'C{i} = Code("{name}")\n' for i, name in enumerate(DECLARED[:6])),
        encoding="utf-8",
    )

    text = _conventions_to_text(compute_conventions(tmp_path), top_n=8)

    assert ", ".join(DECLARED[:6]) in text
    assert "(+" not in text
