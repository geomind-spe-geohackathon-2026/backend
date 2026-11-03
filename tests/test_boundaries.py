"""Import rules that keep the backend's parts apart, found by scanning ``src/``."""

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEMINI_ALLOWED = Path("src/core/gemini")
AGENT_ALLOWED = (Path("src/api/v1/assistant/runs/adapters"), Path("src/core/geomind"))
AGENT_PACKAGES = {"geomind"}
GEMINI_MODULES = {"gemini", "gemini.errors"}
FEATURES = Path("src/api/v1")
LAYOUT = (GEMINI_ALLOWED, *AGENT_ALLOWED)


def imported_modules(path: Path) -> Iterator[tuple[int, str]]:
    """Yield the line and full dotted name of everything a file imports."""
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.lineno, node.module
            for alias in node.names:
                yield node.lineno, f"{node.module}.{alias.name}"


def feature_of(path: Path) -> tuple[str, str] | None:
    """Return the domain and feature that a source file belongs to."""
    parts = path.relative_to(FEATURES).parts if path.is_relative_to(FEATURES) else ()
    return (parts[0], parts[1]) if len(parts) > 2 else None


def imported_feature(module: str) -> tuple[str, str] | None:
    parts = module.split(".")
    if parts[:3] != ["src", "api", "v1"] or len(parts) < 5:
        return None
    return parts[3], parts[4]


def gemini_violation(path: Path, module: str) -> str | None:
    if module.partition(".")[0] != "gemini":
        return None
    if not path.is_relative_to(GEMINI_ALLOWED):
        return "gemini is imported outside src/core/gemini"
    is_name_from_gemini = module.count(".") == 1
    if module in GEMINI_MODULES or is_name_from_gemini:
        return None
    return "only gemini and gemini.errors may be imported"


def agent_violation(path: Path, module: str) -> str | None:
    if module.partition(".")[0] not in AGENT_PACKAGES:
        return None
    if not any(path.is_relative_to(allowed) for allowed in AGENT_ALLOWED):
        return "the agent package is imported outside its adapters and src/core/geomind"
    if module.count(".") <= 1:
        return None
    return "only geomind and geomind.<name> may be imported"


def feature_violation(path: Path, module: str) -> str | None:
    own = feature_of(path)
    other = imported_feature(module)
    if own is None or other is None or own == other:
        return None
    return "features must not import each other"


def violations(root: Path) -> list[str]:
    found = []
    for file in sorted((root / "src").rglob("*.py")):
        path = file.relative_to(root)
        for line, module in imported_modules(file):
            for check in (gemini_violation, agent_violation, feature_violation):
                problem = check(path, module)
                if problem:
                    found.append(f"{path}:{line}: imports {module}: {problem}")
    return found


def write(root: Path, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def test_source_keeps_its_boundaries() -> None:
    assert violations(ROOT) == []


def test_gemini_outside_core_is_found(tmp_path: Path) -> None:
    write(tmp_path, "src/api/v1/a/b/services.py", "import gemini as gm\n")

    assert violations(tmp_path) == [
        "src/api/v1/a/b/services.py:1: imports gemini: "
        "gemini is imported outside src/core/gemini"
    ]


def test_deep_gemini_path_is_found_even_in_core(tmp_path: Path) -> None:
    write(tmp_path, "src/core/gemini/plant.py", "from gemini.core.modules import x\n")

    found = violations(tmp_path)

    assert any("gemini.core.modules" in problem for problem in found)


def test_public_gemini_imports_are_allowed_in_core(tmp_path: Path) -> None:
    source = "import gemini as gm\nimport gemini.errors\nfrom gemini import errors\n"
    write(tmp_path, "src/core/gemini/plant.py", source)

    assert violations(tmp_path) == []


def test_agent_package_is_found_outside_the_adapters(tmp_path: Path) -> None:
    write(tmp_path, "src/core/one.py", "import geomind as gd\n")
    write(tmp_path, "src/core/two.py", "from geomind import Run\n")

    found = violations(tmp_path)

    assert any("src/core/one.py:1: imports geomind" in item for item in found)
    assert any("src/core/two.py:1: imports geomind" in item for item in found)


def test_deep_agent_path_is_found_even_in_adapters(tmp_path: Path) -> None:
    write(
        tmp_path, f"{AGENT_ALLOWED[0]}/agent.py", "from geomind.engine.loop import x\n"
    )

    found = violations(tmp_path)

    assert any("only geomind and geomind.<name>" in problem for problem in found)


def test_public_agent_imports_are_allowed_in_adapters(tmp_path: Path) -> None:
    source = "import geomind as gd\nimport geomind.hooks\nfrom geomind import Run\n"
    write(tmp_path, f"{AGENT_ALLOWED[0]}/agent.py", source)

    assert violations(tmp_path) == []


def test_gemini_is_not_allowed_in_adapters(tmp_path: Path) -> None:
    write(tmp_path, f"{AGENT_ALLOWED[0]}/agent.py", "import gemini as gm\n")

    assert violations(tmp_path)


def test_layout_packages_exist() -> None:
    for folder in LAYOUT:
        assert (ROOT / folder / "__init__.py").is_file()


def test_agent_package_is_allowed_in_adapters(tmp_path: Path) -> None:
    write(tmp_path, f"{AGENT_ALLOWED[0]}/agent.py", "import geomind as gd\n")

    assert violations(tmp_path) == []


def test_feature_importing_another_is_found(tmp_path: Path) -> None:
    write(
        tmp_path,
        "src/api/v1/identity/users/services.py",
        "from src.api.v1.identity.authn import schemas\n",
    )

    found = violations(tmp_path)

    assert found
    assert found[0].startswith("src/api/v1/identity/users/services.py:1: imports")
    assert "features must not import each other" in found[0]


def test_feature_imported_as_a_name_from_its_domain_is_found(tmp_path: Path) -> None:
    write(
        tmp_path,
        "src/api/v1/identity/users/services.py",
        "from src.api.v1.workspace import projects\n",
    )

    assert violations(tmp_path)


def test_feature_may_import_itself_and_domains_may_gather(tmp_path: Path) -> None:
    write(
        tmp_path,
        "src/api/v1/identity/users/router.py",
        "from src.api.v1.identity.users import schemas\n",
    )
    write(
        tmp_path,
        "src/api/v1/identity/__init__.py",
        "from src.api.v1.identity.users.router import router\n",
    )

    assert violations(tmp_path) == []


def test_core_geomind_may_import_geomind(tmp_path: Path) -> None:
    write(tmp_path, f"{AGENT_ALLOWED[1]}/memory.py", "import geomind as gd\n")
    assert violations(tmp_path) == []
