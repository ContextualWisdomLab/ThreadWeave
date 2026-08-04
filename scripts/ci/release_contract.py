"""Validate and materialize deterministic ThreadWeave release evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VERSION_PATTERN = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)
_RELEASE_HEADING = re.compile(
    r"^## \[(?P<version>[^]]+)] - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$",
    re.MULTILINE,
)
_LEVEL_TWO_HEADING = re.compile(r"^## .+$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|UNRELEASED)\b", re.IGNORECASE)


class ReleaseContractError(RuntimeError):
    """Raised when reviewed source cannot produce one unambiguous release."""


@dataclass(frozen=True, slots=True)
class ReleaseContract:
    """Synchronized release metadata extracted from reviewed source."""

    version: str
    tag: str
    release_date: str
    notes: str


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    """Paths and metadata for one deterministic release evidence bundle."""

    contract: ReleaseContract
    notes_path: Path
    checksums_path: Path
    sbom_path: Path
    artifacts: tuple[Path, ...]


def _canonical_version(value: str) -> str:
    """Return one canonical three-part final version or fail closed."""
    if _VERSION_PATTERN.fullmatch(value) is None:
        raise ReleaseContractError(
            "version must be a canonical three-part final release such as 0.2.0"
        )
    return value


def _project_version(root: Path) -> str:
    """Read the static PEP 621 project version from ``pyproject.toml``."""
    path = root / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        value = data["project"]["version"]
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ReleaseContractError(
            "pyproject.toml has no readable project version"
        ) from exc
    if not isinstance(value, str):
        raise ReleaseContractError("pyproject.toml project version must be text")
    return _canonical_version(value)


def _package_version(root: Path) -> str:
    """Read exactly one literal ``__version__`` assignment without importing code."""
    path = root / "src/threadweave/__init__.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise ReleaseContractError(
            "package __version__ source is not readable Python"
        ) from exc

    values: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            values.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__version__"
            and node.value is not None
        ):
            values.append(node.value)
    if len(values) != 1:
        raise ReleaseContractError(
            "package must contain exactly one __version__ assignment"
        )
    value = values[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise ReleaseContractError("package __version__ must be one string literal")
    return _canonical_version(value.value)


def _changelog_release(root: Path, version: str) -> tuple[str, str]:
    """Return the unique release date and material notes for ``version``."""
    path = root / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReleaseContractError("CHANGELOG.md is not readable UTF-8") from exc

    matches = [
        match
        for match in _RELEASE_HEADING.finditer(text)
        if match["version"] == version
    ]
    if not matches:
        raise ReleaseContractError(
            f"CHANGELOG.md has no release section for {version}"
        )
    if len(matches) != 1:
        raise ReleaseContractError(
            f"CHANGELOG.md must contain exactly one release section for {version}"
        )
    match = matches[0]
    next_heading = _LEVEL_TWO_HEADING.search(text, match.end())
    end = len(text) if next_heading is None else next_heading.start()
    notes = text[match.end() : end].strip()
    if not notes:
        raise ReleaseContractError("release notes are empty")
    if _PLACEHOLDER.search(notes) is not None:
        raise ReleaseContractError("release notes contain a placeholder")
    return match["date"], notes


def validate_release(root: Path, requested_version: str) -> ReleaseContract:
    """Validate source metadata and return one synchronized release contract."""
    version = _canonical_version(requested_version)
    project_version = _project_version(root)
    package_version = _package_version(root)
    if project_version != package_version:
        raise ReleaseContractError("project and package version metadata disagrees")
    if version != project_version:
        raise ReleaseContractError(
            "requested version does not match reviewed project metadata"
        )
    release_date, notes = _changelog_release(root, version)
    return ReleaseContract(
        version=version,
        tag=f"v{version}",
        release_date=release_date,
        notes=notes,
    )


def _release_artifacts(dist_dir: Path, version: str) -> tuple[Path, Path]:
    """Return exactly one wheel and one sdist for the reviewed version."""
    try:
        files = [path for path in dist_dir.iterdir() if path.is_file()]
    except OSError as exc:
        raise ReleaseContractError("distribution directory is not readable") from exc
    wheels = sorted(
        path
        for path in files
        if path.name.startswith(f"threadweave-{version}-") and path.suffix == ".whl"
    )
    if len(wheels) > 1:
        raise ReleaseContractError("release requires exactly one wheel")
    sdists = sorted(
        path for path in files if path.name == f"threadweave-{version}.tar.gz"
    )
    if len(sdists) > 1:
        raise ReleaseContractError("release requires exactly one source distribution")
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseContractError(
            "distribution files do not match the reviewed version"
        )
    return wheels[0], sdists[0]


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one release artifact."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ReleaseContractError(
            f"cannot read release artifact: {path.name}"
        ) from exc
    return digest.hexdigest()


def _spdx_document(
    contract: ReleaseContract,
    artifacts: tuple[Path, ...],
    digests: dict[str, str],
) -> dict[str, Any]:
    """Build a deterministic SPDX 2.3 document for ThreadWeave distributions."""
    namespace_seed = "\n".join(
        [contract.version, contract.release_date]
        + [f"{artifact.name}:{digests[artifact.name]}" for artifact in artifacts]
    )
    namespace_digest = hashlib.sha256(namespace_seed.encode("utf-8")).hexdigest()
    package_id = "SPDXRef-Package-threadweave"
    files: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package_id,
        }
    ]
    for index, artifact in enumerate(artifacts, start=1):
        file_id = f"SPDXRef-File-{index}"
        files.append(
            {
                "SPDXID": file_id,
                "fileName": f"dist/{artifact.name}",
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": digests[artifact.name],
                    }
                ],
                "licenseConcluded": "Apache-2.0",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": package_id,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_id,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"threadweave-{contract.version}-release",
        "documentNamespace": (
            "https://spdx.org/spdxdocs/"
            f"threadweave-{contract.version}-{namespace_digest}"
        ),
        "creationInfo": {
            "created": f"{contract.release_date}T00:00:00Z",
            "creators": ["Organization: Contextual Wisdom Lab"],
            "licenseListVersion": "3.25",
        },
        "packages": [
            {
                "SPDXID": package_id,
                "name": "threadweave",
                "versionInfo": contract.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": (
                            f"pkg:pypi/threadweave@{contract.version}"
                        ),
                    }
                ],
            }
        ],
        "files": files,
        "relationships": relationships,
    }


def _require_empty_output(output_dir: Path) -> None:
    """Create an empty output directory or reject stale evidence."""
    try:
        if output_dir.exists():
            if not output_dir.is_dir() or any(output_dir.iterdir()):
                raise ReleaseContractError(
                    "release output directory must be empty"
                )
        else:
            output_dir.mkdir(parents=True)
    except OSError as exc:
        raise ReleaseContractError(
            "release output directory is not usable"
        ) from exc


def prepare_release(
    root: Path,
    version: str,
    dist_dir: Path,
    output_dir: Path,
) -> ReleaseEvidence:
    """Validate and write release notes, checksums, and an SPDX 2.3 SBOM."""
    contract = validate_release(root, version)
    wheel, sdist = _release_artifacts(dist_dir, contract.version)
    artifacts = tuple(sorted((wheel, sdist), key=lambda path: path.name))
    digests = {artifact.name: _sha256(artifact) for artifact in artifacts}
    _require_empty_output(output_dir)

    notes_path = output_dir / "RELEASE_NOTES.md"
    checksums_path = output_dir / "SHA256SUMS.txt"
    sbom_path = output_dir / f"threadweave-{contract.version}.spdx.json"
    try:
        notes_path.write_text(contract.notes + "\n", encoding="utf-8")
        checksums_path.write_text(
            "".join(
                f"{digests[path.name]}  {path.name}\n" for path in artifacts
            ),
            encoding="utf-8",
        )
        sbom_path.write_text(
            json.dumps(
                _spdx_document(contract, artifacts, digests),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ReleaseContractError(
            "release evidence could not be written"
        ) from exc
    return ReleaseEvidence(
        contract=contract,
        notes_path=notes_path,
        checksums_path=checksums_path,
        sbom_path=sbom_path,
        artifacts=artifacts,
    )


def _write_outputs(path: Path | None, evidence: ReleaseEvidence) -> None:
    """Append bounded scalar outputs for downstream GitHub Actions jobs."""
    if path is None:
        return
    contract = evidence.contract
    values = {
        "version": contract.version,
        "tag": contract.tag,
        "release_date": contract.release_date,
        "notes_path": str(evidence.notes_path),
        "checksums_path": str(evidence.checksums_path),
        "sbom_path": str(evidence.sbom_path),
    }
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.writelines(
                f"{key}={value}\n" for key, value in values.items()
            )
    except OSError as exc:
        raise ReleaseContractError(
            "GitHub output file is not writable"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    """Build the command-line interface for trusted release jobs."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--version", required=True)
    prepare.add_argument("--dist-dir", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--github-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the release contract CLI and convert contract failures to exit 2."""
    args = _parser().parse_args(argv)
    try:
        evidence = prepare_release(
            args.root.resolve(),
            args.version,
            args.dist_dir.resolve(),
            args.output_dir.resolve(),
        )
        _write_outputs(
            (
                args.github_output.resolve()
                if args.github_output is not None
                else None
            ),
            evidence,
        )
    except ReleaseContractError as exc:
        print(f"release contract: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
