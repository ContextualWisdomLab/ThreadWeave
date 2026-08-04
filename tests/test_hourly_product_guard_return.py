"""Focused coverage for valid autonomous patch inventory paths."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ci" / "hourly_product_guard.py"
SPEC = importlib.util.spec_from_file_location("hourly_product_guard_return", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_valid_patch_returns_sorted_exact_path_inventory(tmp_path: Path):
    """A safe multi-file patch reaches the successful validation return path."""

    patch = tmp_path / "valid.patch"
    patch.write_text(
        "diff --git a/README.md b/README.md\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n"
        "diff --git a/CHANGELOG.md b/CHANGELOG.md\n"
        "--- a/CHANGELOG.md\n"
        "+++ b/CHANGELOG.md\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n",
        encoding="utf-8",
    )

    assert guard.validate_patch_text(patch) == ["CHANGELOG.md", "README.md"]


def test_regular_new_file_mode_is_a_valid_text_patch(tmp_path: Path):
    """A new non-executable UTF-8 source file may cross the patch boundary."""

    patch = tmp_path / "new-file.patch"
    patch.write_text(
        "diff --git a/tests/test_generated.py b/tests/test_generated.py\n"
        "new file mode 100644\n"
        "index 0000000..c8a7a0f\n"
        "--- /dev/null\n"
        "+++ b/tests/test_generated.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_generated():\n"
        "+    assert True\n",
        encoding="utf-8",
    )

    assert guard.validate_patch_text(patch) == ["tests/test_generated.py"]
