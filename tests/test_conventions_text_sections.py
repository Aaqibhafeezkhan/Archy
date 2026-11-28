"""The `conventions` and `brief` text sections that no test ran (#702).

Reports are built by hand, so each expected line is worked out from the inputs
above it and nothing depends on scan order or the hash seed (#875).
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from archy.cli import main
from archy.cli_render_check import _brief_to_text
from archy.cli_render_conventions import _conventions_to_text, _module_view_to_text
from archy.conventions_models import (
    BaseFamily,
    ConventionsReport,
    DocGap,
    ExportGap,
    Gate,
    ModelCensus,
    ModulePartition,
    ModuleView,
    RegistryEntry,
    SharedConstant,
    SurfaceFamily,
)

# Set by 3 of the family's members: 2 say 1 and 1 says 2.
EXIT_CODE = SharedConstant(
    name="exit_code", setters=3, values=("1", "2"), distribution=(("1", 2), ("2", 1))
)
# One member of five ends in "Error": 20%, below the 80% at which a name is the rule.
MIXED = BaseFamily(
    base="Problem",
    count=6,
    home_module="pkg.errors",
    home_count=6,
    members=("Bad", "Broken", "Gone", "Lost", "Problem", "UsageError"),
    suffixes=("Bad", "Broken", "Error", "Gone", "Lost", "Problem"),
    shared_constants=(EXIT_CODE,),
)
# Every member ends in "Error".
UNIFORM = BaseFamily(
    base="BaseError",
    count=3,
    home_module="pkg.io",
    home_count=3,
    members=("BaseError", "ReadError", "WriteError"),
    suffixes=("Error",),
)
REGISTRY = RegistryEntry(
    constructor="ErrorCode",
    count=80,
    home_module="pkg.codes",
    home_count=79,
    examples=("A", "B"),
    keyword_defaults=(
        SharedConstant(
            name="default_enabled",
            setters=13,
            values=("False",),
            distribution=(("False", 13),),
        ),
    ),
    literal_names=("a", "b"),
)


def _report(**sections: object) -> ConventionsReport:
    empty = {
        "root": "/p",
        "modules_scanned": 4,
        "modules_unparsed": 0,
        "naming": (),
        "surfaces": (),
        "gates": (),
        "errors": (),
        "models": ModelCensus(
            total_classes=0,
            value_classes=0,
            frozen_classes=0,
            base_counts=(),
            config_flags=(),
            tuple_fields=0,
            list_fields=0,
        ),
    }
    return ConventionsReport.model_validate({**empty, **sections})


def _section(text: str, heading: str) -> list[str]:
    """The lines under the heading starting `## {heading}`, up to the blank one."""
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## {heading}"))
    body = lines[start:]
    end = next((i for i, line in enumerate(body) if not line), len(body))
    return body[:end]


PAD = " " * 28


def test_kinds_say_when_the_name_is_not_the_rule():
    text = _conventions_to_text(_report(bases=(MIXED, UNIFORM)), top_n=8)

    assert _section(text, "kinds") == [
        "## kinds - classes grouped by what they derive from (2)",
        f"  {'Problem':<28}   6 @ pkg.errors  <- name is NOT the rule (17% share a suffix)",
        f"  {PAD}     e.g. Bad, Broken, Gone, Lost, Problem",
        f"  {PAD}     exit_code = 1x2, 2x1  (3 of 6 set it)",
        f"  {'BaseError':<28}   3 @ pkg.io",
        f"  {PAD}     e.g. BaseError, ReadError, WriteError",
    ]


def test_registries_count_who_passes_an_argument():
    text = _conventions_to_text(_report(registries=(REGISTRY,)), top_n=8)

    assert _section(text, "registries") == [
        "## registries - values declared by repeated construction (1)",
        f"  {'ErrorCode':<28}  80 @ pkg.codes (79)",
        f"  {PAD}     names: a, b",
        f"  {PAD}     default_enabled = Falsex13  (13 of 80 pass it)",
    ]


def test_empty_kinds_and_registries_say_none():
    text = _conventions_to_text(_report(), top_n=8)

    assert _section(text, "kinds")[1] == (
        "  (none: no base defined in this project has enough subclasses)"
    )
    assert _section(text, "registries")[1] == "  (none)"
    assert "## export gaps" not in text
    assert "## doc gaps" not in text


EXPORT_GAP = ExportGap(
    export_module="pkg", family="Problem", exported=4, defined=6, missing=("Gone", "Lost")
)
DOC_GAP = DocGap(doc_root="docs", family="Problem", documented=5, defined=6, missing=("Lost",))


def test_gaps_name_what_is_missing_and_from_where():
    text = _conventions_to_text(_report(export_gaps=(EXPORT_GAP,), doc_gaps=(DOC_GAP,)), top_n=8)

    assert _section(text, "export gaps") == [
        "## export gaps (1) - defined but not re-exported beside their siblings",
        f"  {'pkg':<28} Problem: 4/6  missing Gone, Lost",
    ]
    assert _section(text, "doc gaps") == [
        "## doc gaps (1) - public members their own docs do not name",
        f"  {'docs/':<28} Problem: 5/6  missing Lost",
    ]


def test_brief_notes_the_weak_name_the_shared_constant_and_the_gaps():
    report = _report(
        bases=(MIXED,),
        export_gaps=(EXPORT_GAP,),
        doc_gaps=(DOC_GAP,),
        docs_scanned=2,
        partition=ModulePartition(production=4, tests=3, shadowed=1, nonsource=2),
    )

    text = _brief_to_text(report, None, None, None, top_n=8)

    assert (
        "#   4 module(s), 2 doc file(s); set aside: 3 test, 2 non-source, 1 duplicating a parent"
        in text
    )
    assert f"  {'Problem':<26}   6 @ pkg.errors  <- name is NOT the rule (17%)" in text
    assert f"  {' ' * 26}     exit_code = 1x2, 2x1  (3 of 6 set it)" in text
    assert "  🔴 pkg: Problem 4/6, missing Gone, Lost" in text
    assert "  🔴 docs/: Problem 5/6, missing Lost" in text
    assert "  (no archy.yaml discovered, so no layer rule governs anything)" in text


def test_brief_says_when_a_config_was_found_but_is_invalid():
    text = _brief_to_text(_report(), None, None, None, top_n=8, coverage_error="layers overlap")

    assert "  archy.yaml found but invalid: layers overlap" in text
    assert "no archy.yaml discovered" not in text


def test_module_view_says_when_a_module_declares_no_exports():
    view = ModuleView(
        module="pkg.a",
        status="censused",
        classes=(),
        functions=(),
        imports_internal=(),
        imported_by=(),
        exports=None,
        suffix_families=(),
        gates=(),
    )

    assert "  exports       (no __all__ and no explicit re-exports)" in _module_view_to_text(view)


def test_module_view_lists_each_exit_with_its_code_and_control():
    gates = (
        Gate(
            module="pkg.a",
            function="main",
            kind="gate",
            code=1,
            control="flag:--strict",
            is_command=True,
            category="gate",
        ),
        Gate(
            module="pkg.a",
            function="load",
            kind="ClickException",
            code=None,
            control="hardcoded",
            is_command=False,
            category="error",
        ),
    )
    view = ModuleView(
        module="pkg.a",
        status="censused",
        classes=(),
        functions=("load", "main"),
        imports_internal=(),
        imported_by=(),
        exports=(),
        suffix_families=(),
        gates=gates,
    )

    lines = _module_view_to_text(view).split("\n")

    start = lines.index("  exits")
    assert lines[start + 1 : start + 3] == [
        f"  {'pkg.a:main':<34} {'gate(1)':<18} flag:--strict  [command]",
        f"  {'pkg.a:load':<34} {'ClickException(?)':<18} hardcoded",
    ]


def test_a_registry_declared_without_literal_names_has_no_names_line():
    bare = REGISTRY.model_copy(update={"literal_names": (), "keyword_defaults": ()})

    text = _conventions_to_text(_report(registries=(bare,)), top_n=8)

    assert _section(text, "registries")[1:] == [f"  {'ErrorCode':<28}  80 @ pkg.codes (79)"]


def _family(base: str, members: tuple[str, ...], *constants: str) -> BaseFamily:
    return BaseFamily(
        base=base,
        count=len(members),
        home_module="pkg.errors",
        home_count=len(members),
        members=members,
        suffixes=("x",),
        shared_constants=tuple(
            SharedConstant(name=n, setters=2, values=("1",), distribution=(("1", 2),))
            for n in constants
        ),
    )


# Four of five end in "Error": exactly the 80% at which a name still counts as the rule.
ON_THE_LINE = _family("Base", ("AError", "BError", "CError", "DError", "Odd"), "a", "b", "c", "d")
THREE = _family("Three", ("OneError", "TwoError", "SixError"))
# Six members, so only the first five are given as examples.
SIX = _family("Six", ("A1Error", "B2Error", "C3Error", "D4Error", "E5Error", "F6Error"))
PAIR = _family("Pair", ("LeftError", "RightError"))


def _registry(name: str, names: int, defaults: int) -> RegistryEntry:
    return RegistryEntry(
        constructor=name,
        count=9,
        home_module="pkg.codes",
        home_count=9,
        examples=(),
        keyword_defaults=tuple(
            SharedConstant(name=f"k{i}", setters=1, values=("0",), distribution=(("0", 1),))
            for i in range(defaults)
        ),
        literal_names=tuple(f"n{i}" for i in range(names)),
    )


def test_kinds_keep_their_order_cut_at_top_n_and_say_how_to_see_the_rest():
    report = _report(bases=(ON_THE_LINE, SIX, THREE))

    section = _section(_conventions_to_text(report, top_n=2), "kinds")

    assert section == [
        "## kinds - classes grouped by what they derive from (3; showing 2, --top 3 for the rest)",
        f"  {'Base':<28}   5 @ pkg.errors",
        f"  {PAD}     e.g. AError, BError, CError, DError, Odd",
        f"  {PAD}     a = 1x2  (2 of 5 set it)",
        f"  {PAD}     b = 1x2  (2 of 5 set it)",
        f"  {PAD}     c = 1x2  (2 of 5 set it)",
        f"  {'Six':<28}   6 @ pkg.errors",
        f"  {PAD}     e.g. A1Error, B2Error, C3Error, D4Error, E5Error",
    ]


def test_registries_cut_rows_names_and_arguments():
    report = _report(registries=(_registry("First", 8, 4), _registry("Second", 1, 0)))

    section = _section(_conventions_to_text(report, top_n=1), "registries")

    assert section == [
        "## registries - values declared by repeated construction "
        "(2; showing 1, --top 2 for the rest)",
        f"  {'First':<28}   9 @ pkg.codes (9)",
        f"  {PAD}     names: n0, n1, n2, n3, n4, n5 (+2)",
        f"  {PAD}     k0 = 0x1  (1 of 9 pass it)",
        f"  {PAD}     k1 = 0x1  (1 of 9 pass it)",
        f"  {PAD}     k2 = 0x1  (1 of 9 pass it)",
    ]


SECOND_EXPORT_GAP = ExportGap(
    export_module="pkg.b", family="Other", exported=2, defined=3, missing=("Z",)
)
SECOND_DOC_GAP = DocGap(doc_root="guide", family="Other", documented=2, defined=3, missing=("Z",))


def test_gap_lists_are_never_cut_by_top_n_and_keep_their_order():
    report = _report(
        export_gaps=(EXPORT_GAP, SECOND_EXPORT_GAP), doc_gaps=(DOC_GAP, SECOND_DOC_GAP)
    )

    text = _conventions_to_text(report, top_n=1)

    assert _section(text, "export gaps")[1:] == [
        f"  {'pkg':<28} Problem: 4/6  missing Gone, Lost",
        f"  {'pkg.b':<28} Other: 2/3  missing Z",
    ]
    assert _section(text, "doc gaps")[1:] == [
        f"  {'docs/':<28} Problem: 5/6  missing Lost",
        f"  {'guide/':<28} Other: 2/3  missing Z",
    ]


def _brief(report: ConventionsReport, top_n: int) -> str:
    return _brief_to_text(report, None, None, None, top_n=top_n)


def test_brief_kinds_need_three_members_and_are_filtered_before_the_cut():
    # PAIR comes first: filtering after the cut would leave only one kind.
    report = _report(bases=(PAIR, ON_THE_LINE, THREE, SIX))

    section = _section(_brief(report, 2), "what kind of thing")

    assert section[1:] == [
        f"  {'Base':<26}   5 @ pkg.errors",
        f"  {' ' * 26}     a = 1x2  (2 of 5 set it)",
        f"  {' ' * 26}     b = 1x2  (2 of 5 set it)",
        f"  {'Three':<26}   3 @ pkg.errors",
    ]


def test_brief_change_with_lists_consumers_only_and_cuts_each_list():
    def surface(kind: str, stem: str) -> SurfaceFamily:
        return SurfaceFamily(kind=kind, stem=stem, module="pkg.m", surfaces=("pkg.x", "pkg.y"))

    report = _report(
        surfaces=(surface("helper", "_h"), surface("consumer", "One"), surface("consumer", "Two")),
        export_gaps=(EXPORT_GAP, SECOND_EXPORT_GAP),
        doc_gaps=(DOC_GAP, SECOND_DOC_GAP),
    )

    section = _section(_brief(report, 1), "what must change")

    assert section[1:] == [
        f"  {'One':<26} pkg.m -> pkg.x, pkg.y",
        "  🔴 pkg: Problem 4/6, missing Gone, Lost",
        "  🔴 docs/: Problem 5/6, missing Lost",
    ]


def test_brief_gates_are_cut_in_order():
    def gate(function: str) -> Gate:
        return Gate(
            module="pkg.a",
            function=function,
            kind="gate",
            code=1,
            control="hardcoded",
            is_command=False,
            category="gate",
        )

    section = _section(_brief(_report(gates=(gate("first"), gate("second"))), 1), "does a new")

    assert section[1:] == [f"  {'pkg.a:first':<34} {'gate(1)':<18} hardcoded"]


def test_brief_headline_leaves_out_what_there_is_none_of():
    report = _report(partition=ModulePartition(production=4, tests=0, shadowed=0))

    assert _brief(report, 8).split("\n")[1] == "#   4 module(s)"


def test_module_view_counts_a_list_only_past_six():
    def view(count: int) -> str:
        return _module_view_to_text(
            ModuleView(
                module="pkg.a",
                status="censused",
                classes=tuple(f"C{i}" for i in range(count)),
                functions=(),
                imports_internal=(),
                imported_by=(),
                exports=(),
                suffix_families=(),
                gates=(),
            )
        )

    assert "  classes       C0, C1, C2, C3, C4, C5\n" in view(6)
    assert "  classes (7)   C0, C1, C2, C3, C4, C5, C6\n" in view(7)


def test_the_command_reaches_these_sections_from_a_real_scan(tmp_path: Path):
    """Hand-built reports above pin the text; this pins that a scan feeds it."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "errors.py").write_text(
        "class Base(Exception): pass\n" + "".join(f"class {n}(Base): pass\n" for n in "ABCD"),
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "__init__.py").write_text(
        'from .errors import Base, A, B\n__all__ = ["Base", "A", "B"]\n', encoding="utf-8"
    )

    result = CliRunner().invoke(main, ["conventions", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert f"  {'Base':<28}   5 @ pkg.errors" in result.output
    assert f"  {'pkg':<28} Base: 3/5  missing C, D" in result.output
