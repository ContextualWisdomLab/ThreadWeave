"""Validate and prepare deterministic evidence for ThreadWeave releases.

The release workflow treats the checked-out source and built distributions as
untrusted until project metadata, package metadata, changelog notes, filenames,
and cryptographic digests agree on one canonical final version.  This module is
standard-library only so it can run after the repository's reviewed CI lock is
installed without adding runtime dependencies to ThreadWeave.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import stat
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_CANONICAL_VERSION = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)
_PROJECT_SECTION = re.compile(r"^\s*\[project\]\s*(?:#.*)?$")
_SECTION = re.compile(r"^\s*\[[^\]]+\]\s*(?:#.*)?$")
_VERSION_ASSIGNMENT = re.compile(
    r"^\s*version\s*=\s*(?P<quote>['\"])(?P<value>[^'\"]+)(?P=quote)\s*(?:#.*)?$"
)
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|Unreleased)\b", re.IGNORECASE)
_PROJECT_NAME = "threadweave"
_LICENSE_EXPRESSION = "Apache-2.0"


class ReleaseContractError(RuntimeError):
    """Raised when source, artifacts, or release evidence fail closed."""


@dataclass(frozen=True, slots=True)
class ReleaseContract:
    """Synchronized source metadata for one canonical final release."""

    version: str
    tag: str
    release_date: str
    notes: str


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    """Paths to deterministic evidence generated for a validated release."""

    contract: ReleaseContract
    notes_path: Path
    checksums_path: Path
    sbom_path: Path


def _read_text(path: Path, label: str, root: Path) -> str:
    """Read one real UTF-8 file contained by the reviewed release root."""

    try:
        trusted_root = root.resolve(strict=True)
        candidate = path.absolute()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(trusted_root)
        relative = candidate.relative_to(trusted_root)
        current = trusted_root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ReleaseContractError(
                    f"{label} must be one regular file inside release root: {path}"
                )
        metadata = candidate.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ReleaseContractError(
                f"{label} must be one regular file inside release root: {path}"
            )
        return resolved.read_text(encoding="utf-8")
    except ReleaseContractError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReleaseContractError(f"could not read {label}: {path}") from exc


def _read_project_version(path: Path, root: Path) -> str:
    """Return the one literal ``[project].version`` value from ``pyproject.toml``."""

    in_project = False
    versions: list[str] = []
    for line in _read_text(path, "project metadata", root).splitlines():
        if _PROJECT_SECTION.fullmatch(line):
            in_project = True
            continue
        if _SECTION.fullmatch(line):
            in_project = False
            continue
        if not in_project:
            continue
        match = _VERSION_ASSIGNMENT.fullmatch(line)
        if match is not None:
            versions.append(match.group("value"))
    if len(versions) != 1:
        raise ReleaseContractError(
            "project metadata must contain exactly one literal [project].version"
        )
    return versions[0]


def _read_package_version(path: Path, root: Path) -> str:
    """Return one top-level literal ``__version__`` assignment from the package."""

    try:
        module = ast.parse(_read_text(path, "package metadata", root), filename=str(path))
    except SyntaxError as exc:
        raise ReleaseContractError("package metadata is not valid Python") from exc

    assignments: list[ast.expr] = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            version_target = any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            )
            if version_target:
                assignments.append(statement.value)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "__version__"
            and statement.value is not None
        ):
            assignments.append(statement.value)
    if not assignments:
        raise ReleaseContractError("package metadata has no __version__ assignment")
    if len(assignments) != 1:
        raise ReleaseContractError(
            "package metadata must contain exactly one __version__ assignment"
        )
    value = assignments[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise ReleaseContractError("package __version__ must be one string literal")
    return value.value


def _read_changelog(path: Path, version: str, root: Path) -> tuple[str, str]:
    """Return final release notes only when the Unreleased section is empty."""

    text = _read_text(path, "changelog", root)
    unreleased = re.search(r"^## Unreleased\s*$", text, re.MULTILINE)
    if unreleased is not None:
        following_unreleased = re.search(
            r"^## ", text[unreleased.end() :], re.MULTILINE
        )
        unreleased_end = (
            unreleased.end() + following_unreleased.start()
            if following_unreleased is not None
            else len(text)
        )
        if text[unreleased.end() : unreleased_end].strip():
            raise ReleaseContractError(
                "changelog has material Unreleased notes for a final release"
            )

    header = re.compile(
        rf"^## \[{re.escape(version)}\] - (?P<date>[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})\s*$",
        re.MULTILINE,
    )
    matches = list(header.finditer(text))
    if not matches:
        raise ReleaseContractError(f"changelog has no release section for {version}")
    if len(matches) != 1:
        raise ReleaseContractError(
            f"changelog must contain exactly one release section for {version}"
        )
    match = matches[0]
    release_date = match.group("date")
    try:
        date.fromisoformat(release_date)
    except ValueError as exc:
        raise ReleaseContractError("changelog release date is not a valid ISO date") from exc

    following = re.search(r"^## ", text[match.end() :], re.MULTILINE)
    end = match.end() + following.start() if following is not None else len(text)
    notes = text[match.end() : end].strip()
    if not notes:
        raise ReleaseContractError("changelog release notes are empty")
    if _PLACEHOLDER.search(notes):
        raise ReleaseContractError("changelog release notes contain a placeholder")
    return release_date, notes


def validate_release(root: Path, requested_version: str) -> ReleaseContract:
    """Validate source metadata and return one immutable release contract."""

    if _CANONICAL_VERSION.fullmatch(requested_version) is None:
        raise ReleaseContractError(
            "requested version must be a canonical three-part final version"
        )
    trusted_root = root.resolve(strict=True)
    project_version = _read_project_version(
        trusted_root / "pyproject.toml", trusted_root
    )
    package_version = _read_package_version(
        trusted_root / "src/threadweave/__init__.py", trusted_root
    )
    if project_version != package_version:
        raise ReleaseContractError("project and package version metadata disagrees")
    if requested_version != project_version:
        raise ReleaseContractError(
            "requested version does not match the reviewed project version"
        )
    release_date, notes = _read_changelog(
        trusted_root / "CHANGELOG.md", requested_version, trusted_root
    )
    return ReleaseContract(
        version=requested_version,
        tag=f"v{requested_version}",
        release_date=release_date,
        notes=notes,
    )


def _artifact_digests(path: Path) -> tuple[str, str]:
    """Return SPDX-required SHA-1 and security-grade SHA-256 file digests."""

    # SPDX 2.3 requires one SHA-1 file checksum. ``usedforsecurity=False``
    # makes explicit that SHA-1 is emitted only for standards interoperability;
    # SHA-256 remains the release-integrity digest.
    sha1 = hashlib.new("sha1", usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha1.update(chunk)
            sha256.update(chunk)
    return sha1.hexdigest(), sha256.hexdigest()


def _release_artifacts(dist_dir: Path, version: str) -> list[tuple[Path, str, str]]:
    """Return exactly one reviewed wheel and one reviewed source archive."""

    if dist_dir.is_symlink() or not dist_dir.is_dir():
        raise ReleaseContractError(
            f"distribution directory must be one real directory: {dist_dir}"
        )
    try:
        candidates = sorted(dist_dir.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise ReleaseContractError(
            f"could not inspect distribution directory: {dist_dir}"
        ) from exc

    wheels = [path for path in candidates if path.name.endswith(".whl")]
    source_archives = [path for path in candidates if path.name.endswith(".tar.gz")]
    if len(wheels) != 1:
        raise ReleaseContractError("distribution directory must contain exactly one wheel")
    if len(source_archives) != 1:
        raise ReleaseContractError(
            "distribution directory must contain exactly one source archive"
        )

    wheel = wheels[0]
    source_archive = source_archives[0]
    expected_wheel = re.compile(
        rf"threadweave-{re.escape(version)}-[A-Za-z0-9_.-]+\.whl"
    )
    if expected_wheel.fullmatch(wheel.name) is None or source_archive.name != (
        f"threadweave-{version}.tar.gz"
    ):
        raise ReleaseContractError(
            "distribution filenames do not match the reviewed version"
        )

    results: list[tuple[Path, str, str]] = []
    for artifact in (wheel, source_archive):
        try:
            metadata = artifact.lstat()
        except OSError as exc:
            raise ReleaseContractError(
                f"could not inspect release artifact: {artifact}"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ReleaseContractError(
                f"release artifact must be one regular non-linked file: {artifact.name}"
            )
        sha1, sha256 = _artifact_digests(artifact)
        results.append((artifact, sha1, sha256))
    return sorted(results, key=lambda item: item[0].name)


def _package_verification_code(artifacts: list[tuple[Path, str, str]]) -> str:
    """Return the SPDX 2.3 package verification code for release files."""

    concatenated_sha1 = "".join(sorted(sha1 for _path, sha1, _sha256 in artifacts))
    verifier = hashlib.new(
        "sha1",
        concatenated_sha1.encode("ascii"),
        usedforsecurity=False,
    )
    return verifier.hexdigest()


def _spdx_document(
    contract: ReleaseContract,
    artifacts: list[tuple[Path, str, str]],
) -> dict[str, object]:
    """Return a deterministic, schema-conformant SPDX 2.3 release document."""

    package_id = "SPDXRef-Package-ThreadWeave"
    manifest = "\n".join(
        f"{path.name}:{sha256}" for path, _sha1, sha256 in artifacts
    )
    namespace_digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    files = [
        {
            "SPDXID": f"SPDXRef-File-{index}",
            "checksums": [
                {"algorithm": "SHA1", "checksumValue": sha1},
                {"algorithm": "SHA256", "checksumValue": sha256},
            ],
            "copyrightText": "NOASSERTION",
            "fileName": f"dist/{path.name}",
            "fileTypes": ["ARCHIVE"],
            "licenseConcluded": _LICENSE_EXPRESSION,
        }
        for index, (path, sha1, sha256) in enumerate(artifacts, start=1)
    ]
    file_ids = [str(item["SPDXID"]) for item in files]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package_id,
        }
    ]
    relationships.extend(
        {
            "spdxElementId": package_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": file_id,
        }
        for file_id in file_ids
    )
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": f"{contract.release_date}T00:00:00Z",
            "creators": [
                "Organization: Contextual Wisdom Lab",
                "Tool: ThreadWeave-release-contract",
            ],
        },
        "dataLicense": "CC0-1.0",
        "documentDescribes": [package_id],
        "documentNamespace": (
            "https://github.com/ContextualWisdomLab/ThreadWeave/spdxdocs/"
            f"{contract.tag}/{namespace_digest}"
        ),
        "files": files,
        "name": f"threadweave-{contract.version}-release",
        "packages": [
            {
                "SPDXID": package_id,
                "copyrightText": "NOASSERTION",
                "downloadLocation": (
                    f"https://pypi.org/project/threadweave/{contract.version}/"
                ),
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": f"pkg:pypi/threadweave@{contract.version}",
                        "referenceType": "purl",
                    }
                ],
                "filesAnalyzed": True,
                "hasFiles": file_ids,
                "licenseConcluded": _LICENSE_EXPRESSION,
                "licenseDeclared": _LICENSE_EXPRESSION,
                "licenseInfoFromFiles": [_LICENSE_EXPRESSION],
                "name": _PROJECT_NAME,
                "packageVerificationCode": {
                    "packageVerificationCodeValue": _package_verification_code(
                        artifacts
                    )
                },
                "primaryPackagePurpose": "LIBRARY",
                "supplier": "Organization: Contextual Wisdom Lab",
                "versionInfo": contract.version,
            }
        ],
        "relationships": relationships,
        "spdxVersion": "SPDX-2.3",
    }


def _prepare_output_directory(output_dir: Path) -> None:
    """Create an empty evidence directory without following symbolic links."""

    if output_dir.is_symlink():
        raise ReleaseContractError("release output directory must not be a symbolic link")
    if output_dir.exists():
        if not output_dir.is_dir() or any(output_dir.iterdir()):
            raise ReleaseContractError("release output directory must be absent or empty")
    else:
        output_dir.mkdir(parents=True)


def prepare_release(
    root: Path,
    version: str,
    dist_dir: Path,
    output_dir: Path,
) -> ReleaseEvidence:
    """Validate a release and write deterministic notes, checksums, and SPDX JSON."""

    contract = validate_release(root.resolve(), version)
    artifacts = _release_artifacts(dist_dir, version)
    _prepare_output_directory(output_dir)

    notes_path = output_dir / "release-notes.md"
    checksums_path = output_dir / "SHA256SUMS.txt"
    sbom_path = output_dir / f"threadweave-{version}.spdx.json"
    notes_path.write_text(contract.notes + "\n", encoding="utf-8")
    checksums_path.write_text(
        "".join(
            f"{sha256}  {path.name}\n"
            for path, _sha1, sha256 in artifacts
        ),
        encoding="utf-8",
    )
    sbom_path.write_text(
        json.dumps(_spdx_document(contract, artifacts), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return ReleaseEvidence(
        contract=contract,
        notes_path=notes_path,
        checksums_path=checksums_path,
        sbom_path=sbom_path,
    )


def _write_github_outputs(path: Path | None, evidence: ReleaseEvidence) -> None:
    """Append bounded scalar release outputs for later workflow jobs."""

    if path is None:
        return
    values = {
        "version": evidence.contract.version,
        "tag": evidence.contract.tag,
        "release_date": evidence.contract.release_date,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for release preparation."""

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
    """Prepare release evidence, returning exit code 2 for contract failures."""

    args = _parser().parse_args(argv)
    try:
        evidence = prepare_release(
            args.root,
            args.version,
            args.dist_dir,
            args.output_dir,
        )
        _write_github_outputs(args.github_output, evidence)
    except (ReleaseContractError, OSError) as exc:
        print(f"release contract: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
