"""Read-only GitHub Actions registry lifecycle evidence for ThreadWeave.

This module answers one question without gaining any mutation authority:
which GitHub Actions workflow identities registered against this repository
are backed by exact protected-main source, temporarily owned by a current
same-repository pull-request head, disabled, GitHub-owned/dynamic, confirmed
active orphans, or unresolved (malformed/ambiguous evidence)?

It never disables, restores, or writes a workflow. A separate authorized
operator or control-plane path may use the emitted report only after
independently revalidating the exact live registry state
(see ``docs/superpowers/specs/2026-08-12-actions-registry-audit-design.md``).

Every network call goes through :class:`GitHubJsonClient`, which is the only
place this module touches a live host. Every other function accepts already
-fetched Python data (or an injected client) so the classification and
pagination logic can be exercised deterministically without credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

#: The GitHub REST API version this client requests. GitHub requires this
#: header on every REST call and versions its response shape by it (GitHub,
#: 2026a).
API_VERSION = "2026-03-10"

#: Workflow-list page size. GitHub's documented maximum ``per_page`` value.
WORKFLOWS_PER_PAGE = 100

#: Pull-request-list page size, matching ``WORKFLOWS_PER_PAGE``.
PULLS_PER_PAGE = 100

#: Hard ceiling on pages fetched per endpoint. A well-formed organization
#: repository has at most a few dozen workflows or open PRs; anything beyond
#: this indicates a pagination bug or a hostile/looping response rather than
#: a legitimate registry, so the auditor fails closed instead of looping
#: forever (GitHub, 2026b).
MAX_PAGES = 50

#: Hard ceiling on a single HTTP response body, in bytes. Bounds memory use
#: against a malformed or hostile oversized response.
MAX_RESPONSE_BYTES = 5_000_000

#: Schema identifier embedded in every emitted report.
REPORT_SCHEMA = "threadweave.actions-registry-audit/v1"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$"
)
_WORKFLOW_PATH_RE = re.compile(
    r"^\.github/workflows/[A-Za-z0-9][A-Za-z0-9._-]*\.(?:yml|yaml)$"
)

_FINITE_CLASSIFICATIONS = (
    "present_active",
    "present_disabled",
    "active_pr_workflow",
    "orphan_active",
    "orphan_disabled",
    "dynamic_owned",
    "unresolved",
)


class AuditError(Exception):
    """Raised when Actions registry evidence cannot be safely established.

    Every fail-closed path in this module (malformed identity, incomplete
    pagination, truncated tree, drifted branch, HTTP failure, ...) raises
    this single exception type so callers have exactly one thing to catch.
    """


class HttpStatusError(AuditError):
    """Raised by an injected opener when a GitHub API call returns a non-2xx status."""

    def __init__(self, *, url: str, status: int) -> None:
        """Record the failing URL and status for redacted diagnostics."""
        super().__init__(f"GitHub API request failed with status {status}")
        self.url = url
        self.status = status


def normalize_repository(value: object) -> str:
    """Return ``value`` unchanged if it is exact canonical ``owner/name`` text.

    Args:
        value: The candidate repository identity.

    Returns:
        The same string, proving it already matched the canonical form.

    Raises:
        AuditError: If ``value`` is not a string, or is not exactly one
            ``owner`` segment, one ``/``, and one ``name`` segment built from
            ASCII letters, digits, ``.``, ``_``, and ``-`` (GitHub's allowed
            repository/owner character set), with no leading/trailing
            separator and no embedded whitespace or control characters.
    """
    if not isinstance(value, str) or not _REPO_RE.match(value):
        raise AuditError(f"invalid repository identity: {value!r}")
    return value


def normalize_sha(value: object, *, label: str) -> str:
    """Return ``value`` unchanged if it is an exact lowercase 40-hex Git SHA.

    Args:
        value: The candidate commit identity.
        label: A short description of what this SHA identifies, used only in
            the raised error message (e.g. ``"head"``, ``"protected-main"``).

    Returns:
        The same string, proving it already matched the canonical form.

    Raises:
        AuditError: If ``value`` is not a string of exactly 40 lowercase hex
            characters. Uppercase, short, long, or non-hex values are
            rejected rather than normalized, so two different-cased
            spellings of the same commit can never silently compare equal.
    """
    if not isinstance(value, str) or not _SHA_RE.match(value):
        raise AuditError(f"invalid {label} SHA: {value!r}")
    return value


def normalize_workflow_path(value: object) -> str:
    """Return ``value`` unchanged if it is an exact repository workflow path.

    Args:
        value: The candidate path, as reported by the GitHub Actions or Git
            trees API.

    Returns:
        The same string, proving it already matched the canonical form.

    Raises:
        AuditError: If ``value`` is not a string; is not already in Unicode
            Normalization Form C (so two byte-different spellings of a
            visually identical path can never silently compare equal); or
            does not match ``.github/workflows/<name>.yml`` /
            ``.github/workflows/<name>.yaml`` exactly, with no backslashes,
            null bytes, other control characters, duplicate path
            separators, or ``..`` traversal segments.
    """
    if not isinstance(value, str):
        raise AuditError(f"invalid workflow path: {value!r}")
    if unicodedata.normalize("NFC", value) != value:
        raise AuditError(f"workflow path is not NFC-normalized: {value!r}")
    if ".." in value.split("/") or "//" in value or "\\" in value:
        raise AuditError(f"invalid workflow path: {value!r}")
    if not _WORKFLOW_PATH_RE.match(value):
        raise AuditError(f"invalid workflow path: {value!r}")
    return value


@dataclass(frozen=True)
class ClassifiedWorkflow:
    """One workflow registry record with its finite lifecycle classification.

    Attributes:
        workflow_id: The GitHub Actions numeric workflow identity.
        name: The workflow's display name, as reported by GitHub.
        path: The workflow's repository path, or ``None`` for a
            ``dynamic_owned`` or malformed record with no usable path.
        state: The raw GitHub-reported state string (e.g. ``"active"``).
        classification: One of :data:`_FINITE_CLASSIFICATIONS`.
        reason: A short human-readable explanation of the classification.
    """

    workflow_id: object
    name: object
    path: object
    state: object
    classification: str
    reason: str


def classify_workflow_records(
    records: Sequence[Mapping[str, Any]],
    *,
    protected_paths: Iterable[str],
    active_pr_paths: Iterable[str],
) -> list[ClassifiedWorkflow]:
    """Classify every registry record into exactly one finite bucket.

    Args:
        records: Raw workflow objects as returned by the GitHub Actions
            "list repository workflows" endpoint.
        protected_paths: Exact workflow paths present in the protected-main
            Git tree.
        active_pr_paths: Exact workflow paths present on the head tree of
            any currently open, same-repository pull request.

    Returns:
        One :class:`ClassifiedWorkflow` per input record, in input order.
        A record is ``unresolved`` if its ``id`` is not a positive integer
        (or is a ``bool``, since ``bool`` is a ``int`` subclass in Python and
        would otherwise silently pass an ``int`` check), if its ``id``
        collides with another record's ``id``, or if its ``name``/``path``/
        ``state`` fields are missing or malformed. A record whose path
        parses but does not match the repository workflow-path shape is
        ``dynamic_owned`` (GitHub reports non-repository-path identities,
        such as externally managed dynamic workflows, this way).
    """
    protected = set(protected_paths)
    active_pr = set(active_pr_paths)

    seen_ids: dict[object, int] = {}
    for record in records:
        if isinstance(record, Mapping) and "id" in record:
            raw_id = record["id"]
            if isinstance(raw_id, int) and not isinstance(raw_id, bool) and raw_id > 0:
                seen_ids[raw_id] = seen_ids.get(raw_id, 0) + 1

    results: list[ClassifiedWorkflow] = []
    for record in records:
        if not isinstance(record, Mapping):
            results.append(
                ClassifiedWorkflow(None, None, None, None, "unresolved", "not an object")
            )
            continue

        raw_id = record.get("id")
        name = record.get("name")
        path = record.get("path")
        state = record.get("state")

        if not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id <= 0:
            results.append(
                ClassifiedWorkflow(raw_id, name, path, state, "unresolved", "invalid workflow id")
            )
            continue
        if seen_ids.get(raw_id, 0) > 1:
            results.append(
                ClassifiedWorkflow(raw_id, name, path, state, "unresolved", "duplicate workflow id")
            )
            continue
        if not isinstance(name, str) or not isinstance(state, str) or not state:
            results.append(
                ClassifiedWorkflow(raw_id, name, path, state, "unresolved", "missing name/state")
            )
            continue

        try:
            normalized_path = normalize_workflow_path(path)
        except AuditError:
            results.append(
                ClassifiedWorkflow(raw_id, name, path, state, "dynamic_owned", "non-repository-path identity")
            )
            continue

        is_active = state == "active"
        if normalized_path in protected:
            classification = "present_active" if is_active else "present_disabled"
            reason = "backed by protected-main source"
        elif normalized_path in active_pr:
            classification = "active_pr_workflow"
            reason = "backed by a current same-repository open-PR head"
        else:
            classification = "orphan_active" if is_active else "orphan_disabled"
            reason = "absent from protected main and every open-PR head"

        results.append(
            ClassifiedWorkflow(raw_id, name, normalized_path, state, classification, reason)
        )

    return results


def recommended_disable_workflow_ids(records: Sequence[ClassifiedWorkflow]) -> list[int]:
    """Return the sorted, deduplicated IDs of confirmed active orphan workflows.

    Args:
        records: Classified workflow records, typically from
            :func:`classify_workflow_records`.

    Returns:
        Every ``orphan_active`` record's ``workflow_id``, sorted ascending.
        This list is evidence only: this module never disables a workflow
        itself.
    """
    ids = {r.workflow_id for r in records if r.classification == "orphan_active"}
    return sorted(ids)  # type: ignore[type-var]


@dataclass(frozen=True)
class PageReceipts:
    """Pagination evidence for one paginated GitHub API listing.

    Attributes:
        pages_fetched: How many pages were actually requested.
        total_count: The ``total_count`` GitHub reported alongside the
            first page, when the endpoint provides one.
    """

    pages_fetched: int
    total_count: int | None


class _JsonGetter:
    """Structural type for anything exposing a paginated ``.get`` method."""

    def get(self, path: str, *, params: Mapping[str, object] | None = None) -> Any:
        """Fetch and return one parsed JSON resource; see :meth:`GitHubJsonClient.get`."""
        ...  # pragma: no cover - structural protocol, not executed


def list_workflow_records(
    client: _JsonGetter, repository: str
) -> tuple[list[dict[str, Any]], PageReceipts]:
    """Fetch the complete, verified workflow registry for ``repository``.

    Args:
        client: Any object exposing ``get(path, *, params=None) -> dict``.
        repository: Exact canonical ``owner/name`` identity.

    Returns:
        The complete list of raw workflow objects (across every page), and
        the pagination receipts that prove the walk was complete.

    Raises:
        AuditError: If a page is malformed, if GitHub's own ``total_count``
            disagrees with what was actually collected, if a later page
            byte-for-byte repeats an earlier page (a sign of a broken or
            looping pagination cursor), or if more than :data:`MAX_PAGES`
            pages would be required.
    """
    records: list[dict[str, Any]] = []
    seen_pages: set[tuple[tuple[Any, ...], ...]] = set()
    total_count: int | None = None
    page = 1
    while True:
        if page > MAX_PAGES:
            raise AuditError(f"workflow pagination exceeded {MAX_PAGES} pages")
        response = client.get(
            f"/repos/{repository}/actions/workflows",
            params={"per_page": WORKFLOWS_PER_PAGE, "page": page},
        )
        if not isinstance(response, Mapping):
            raise AuditError("malformed workflow list response")
        page_workflows = response.get("workflows")
        if not isinstance(page_workflows, list):
            raise AuditError("malformed workflow list page")
        if page == 1:
            total_count = response.get("total_count")
            if not isinstance(total_count, int) or isinstance(total_count, bool):
                raise AuditError("malformed workflow list total_count")

        fingerprint = tuple(
            (w.get("id"),) if isinstance(w, Mapping) else (None,) for w in page_workflows
        )
        if fingerprint and fingerprint in seen_pages:
            raise AuditError("workflow pagination returned a repeated page")
        if fingerprint:
            seen_pages.add(fingerprint)

        records.extend(page_workflows)
        if len(page_workflows) < WORKFLOWS_PER_PAGE:
            break
        page += 1

    if total_count is not None and len(records) != total_count:
        raise AuditError(
            f"workflow total_count mismatch: reported {total_count}, collected {len(records)}"
        )
    return records, PageReceipts(pages_fetched=page, total_count=total_count)


@dataclass(frozen=True)
class OpenPullRequest:
    """One open, same-repository pull request head.

    Attributes:
        number: The pull request number.
        head_sha: The exact 40-hex head commit SHA.
    """

    number: int
    head_sha: str


def list_open_pull_requests(
    client: _JsonGetter, repository: str
) -> tuple[list[OpenPullRequest], PageReceipts]:
    """Fetch every open, same-repository pull request head for ``repository``.

    Args:
        client: Any object exposing ``get(path, *, params=None) -> list``.
        repository: Exact canonical ``owner/name`` identity.

    Returns:
        Every open pull request whose head repository is exactly
        ``repository`` (fork-head PRs, and PRs whose head repository was
        deleted and now reports ``null``, are silently excluded — this
        auditor only trusts same-repository source), and pagination
        receipts.

    Raises:
        AuditError: If a page is malformed, a same-repository PR's head SHA
            is not an exact 40-hex identity, or pagination would exceed
            :data:`MAX_PAGES`.
    """
    pulls: list[OpenPullRequest] = []
    page = 1
    while True:
        if page > MAX_PAGES:
            raise AuditError(f"pull request pagination exceeded {MAX_PAGES} pages")
        response = client.get(
            f"/repos/{repository}/pulls",
            params={"state": "open", "per_page": PULLS_PER_PAGE, "page": page},
        )
        if not isinstance(response, list):
            raise AuditError("malformed pull request list page")

        for entry in response:
            if not isinstance(entry, Mapping):
                raise AuditError("malformed pull request entry")
            head = entry.get("head")
            number = entry.get("number")
            if not isinstance(head, Mapping) or not isinstance(number, int) or isinstance(number, bool):
                raise AuditError(f"malformed pull request head for #{number!r}")
            if "repo" not in head:
                raise AuditError(f"malformed pull request head for #{number!r}: missing repo")
            head_repo = head["repo"]
            if head_repo is None:
                continue  # head repository deleted (e.g. fork removed); untrusted, skip
            if not isinstance(head_repo, Mapping):
                raise AuditError(f"malformed pull request head repo for #{number!r}")
            if head_repo.get("full_name") != repository:
                continue  # fork PR; untrusted head source
            head_sha = normalize_sha(head.get("sha"), label=f"PR #{number} head")
            pulls.append(OpenPullRequest(number=number, head_sha=head_sha))

        if len(response) < PULLS_PER_PAGE:
            break
        page += 1

    return pulls, PageReceipts(pages_fetched=page, total_count=None)


def workflow_paths_from_tree(client: _JsonGetter, repository: str, tree_sha: str) -> set[str]:
    """Return every exact ``.github/workflows/*`` blob path in one Git tree.

    Args:
        client: Any object exposing ``get(path, *, params=None) -> dict``.
        repository: Exact canonical ``owner/name`` identity.
        tree_sha: Exact 40-hex commit or tree SHA to read recursively.

    Returns:
        The set of workflow-shaped blob paths found in the tree. A path
        present in the tree but not matching the canonical workflow-path
        shape (per :func:`normalize_workflow_path`) is silently excluded
        rather than raising, since the tree may legitimately contain other
        `.github/workflows/`-adjacent content (this function only needs the
        paths that *could* correspond to a registry record's exact path).

    Raises:
        AuditError: If the tree response is malformed or GitHub reports it
            as ``truncated`` (an incomplete tree cannot prove a workflow's
            absence, so this fails closed rather than silently under
            -reporting).
    """
    response = client.get(f"/repos/{repository}/git/trees/{tree_sha}", params={"recursive": 1})
    if not isinstance(response, Mapping):
        raise AuditError("malformed Git tree response")
    if response.get("truncated"):
        raise AuditError(f"Git tree {tree_sha} is truncated; cannot prove workflow absence")
    entries = response.get("tree")
    if not isinstance(entries, list):
        raise AuditError("malformed Git tree entries")

    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("type") != "blob":
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path.startswith(".github/workflows/"):
            continue
        try:
            paths.add(normalize_workflow_path(path))
        except AuditError:
            continue
    return paths


def audit_actions_registry(client: _JsonGetter, repository: str) -> dict[str, Any]:
    """Run the complete read-only Actions registry lifecycle audit.

    Args:
        client: Any object exposing ``get(path, *, params=None)``, used for
            every GitHub API call this function makes.
        repository: Exact canonical ``owner/name`` identity.

    Returns:
        A JSON-serializable, schema-``v1`` evidence report: repository,
        protected-main SHA, per-workflow classifications (sorted by
        ``workflow_id`` for determinism), a summary count per
        classification, and ``recommended_disable_workflow_ids``.

    Raises:
        AuditError: If any underlying fetch, pagination, or tree read fails
            closed, or if the protected-main default-branch SHA observed at
            the start of the audit differs from the SHA observed again at
            the end (a race between two reads that could otherwise bind
            evidence to a branch state that no longer exists).
    """
    repository = normalize_repository(repository)

    branch = client.get(f"/repos/{repository}/branches/main")
    if not isinstance(branch, Mapping):
        raise AuditError("malformed branch response")
    commit = branch.get("commit")
    if not isinstance(commit, Mapping):
        raise AuditError("malformed branch commit")
    protected_main_sha = normalize_sha(commit.get("sha"), label="protected-main")

    workflow_records, workflow_receipts = list_workflow_records(client, repository)
    pull_requests, pr_receipts = list_open_pull_requests(client, repository)
    protected_paths = workflow_paths_from_tree(client, repository, protected_main_sha)

    active_pr_paths: set[str] = set()
    for pr in pull_requests:
        active_pr_paths |= workflow_paths_from_tree(client, repository, pr.head_sha)

    classified = classify_workflow_records(
        workflow_records, protected_paths=protected_paths, active_pr_paths=active_pr_paths
    )
    classified.sort(key=lambda r: (r.workflow_id is None, r.workflow_id))

    revalidation_branch = client.get(f"/repos/{repository}/branches/main")
    if not isinstance(revalidation_branch, Mapping):
        raise AuditError("malformed branch revalidation response")
    revalidation_commit = revalidation_branch.get("commit")
    if not isinstance(revalidation_commit, Mapping):
        raise AuditError("malformed branch revalidation commit")
    revalidation_sha = normalize_sha(
        revalidation_commit.get("sha"), label="protected-main revalidation"
    )
    if revalidation_sha != protected_main_sha:
        raise AuditError(
            "protected-main moved during the audit: "
            f"{protected_main_sha} -> {revalidation_sha}"
        )

    summary: dict[str, int] = {}
    for record in classified:
        summary[record.classification] = summary.get(record.classification, 0) + 1

    return {
        "schema": REPORT_SCHEMA,
        "repository": repository,
        "protected_main_sha": protected_main_sha,
        "api_version": API_VERSION,
        "workflow_pagination": {
            "pages_fetched": workflow_receipts.pages_fetched,
            "total_count": workflow_receipts.total_count,
        },
        "pull_request_pagination": {
            "pages_fetched": pr_receipts.pages_fetched,
        },
        "open_pull_request_heads": [
            {"number": pr.number, "head_sha": pr.head_sha} for pr in pull_requests
        ],
        "records": [
            {
                "workflow_id": r.workflow_id,
                "name": r.name,
                "path": r.path,
                "state": r.state,
                "classification": r.classification,
                "reason": r.reason,
            }
            for r in classified
        ],
        "summary": summary,
        "recommended_disable_workflow_ids": recommended_disable_workflow_ids(classified),
    }


def encode_report(report: Mapping[str, Any]) -> bytes:
    """Serialize a report deterministically as sorted, compact UTF-8 JSON.

    Args:
        report: A JSON-serializable mapping, typically from
            :func:`audit_actions_registry`.

    Returns:
        UTF-8 encoded bytes. Keys are sorted and separators are compact so
        two runs over identical evidence produce byte-identical output.
    """
    return json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_report_atomically(path: Path, report: Mapping[str, Any]) -> None:
    """Write ``report`` to ``path`` atomically, leaving no partial file behind.

    Args:
        path: Destination file path. Its parent directory must already
            exist.
        report: A JSON-serializable mapping to write.

    The report is written to a sibling temporary file in the same
    directory (so the final :func:`os.replace` is an atomic same
    -filesystem rename) and only then renamed onto ``path``. A reader can
    never observe a truncated or half-written report.
    """
    data = encode_report(report)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class GitHubJsonClient:
    """A minimal, strict, credential-bearing JSON client for the GitHub REST API.

    This is the only place in this module that performs network I/O (or, in
    tests, calls an injected ``opener``). It enforces the API version
    header, a bounded response size, strict UTF-8 decoding, and rejection of
    duplicate JSON object keys (a well-formed but ambiguous document that
    could otherwise let two different fields silently shadow each other).
    """

    def __init__(
        self,
        *,
        token: str,
        opener: Callable[[str, Mapping[str, str]], bytes] | None = None,
        base_url: str = "https://api.github.com",
    ) -> None:
        """Create a client bound to one bearer token and base URL.

        Args:
            token: A GitHub API bearer token. Must be non-empty.
            opener: Injected for tests: a callable taking ``(url, headers)``
                and returning the raw response body bytes, raising
                :class:`HttpStatusError` on a non-2xx status. Defaults to a
                real ``urllib.request`` call.
            base_url: The API host to prefix every request path with.

        Raises:
            AuditError: If ``token`` is empty.
        """
        if not token:
            raise AuditError("GitHub API token is required")
        self._token = token
        self._opener = opener or self._urllib_opener
        self._base_url = base_url

    def _urllib_opener(self, url: str, headers: Mapping[str, str]) -> bytes:
        """Perform the real HTTP GET this client uses by default.

        Args:
            url: The complete request URL, including any query string.
            headers: Request headers to send.

        Returns:
            Up to ``MAX_RESPONSE_BYTES + 1`` bytes of the response body (one
            byte beyond the limit so the caller can distinguish "exactly at
            the limit" from "over the limit" without a second read).

        Raises:
            AuditError: If ``url`` does not use the ``https`` scheme.
                ``urllib`` also honors ``file://`` and other schemes, which
                would let a caller-controlled base URL read the local
                filesystem instead of calling the GitHub API; this client
                only ever calls GitHub over HTTPS.
            HttpStatusError: If the server returns a non-2xx status.
        """
        if not url.startswith("https://"):
            raise AuditError(f"refusing non-https GitHub API URL: {url!r}")
        request = urllib.request.Request(url, headers=dict(headers))
        try:
            # The scheme is checked immediately above, so a hostile "file://"
            # or similar redirect cannot reach urlopen. `_base_url` defaults
            # to the literal "https://api.github.com" and the sole production
            # caller (`_build_client_from_env`) never overrides it; only the
            # path/query built from already-validated repository/SHA/path
            # identities varies.
            with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected  # nosec B310
                request, timeout=30
            ) as response:
                return response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise HttpStatusError(url=url, status=error.code) from error

    def get(self, path: str, *, params: Mapping[str, object] | None = None) -> Any:
        """Fetch and strictly parse one JSON GitHub API resource.

        Args:
            path: The API path, beginning with ``/``.
            params: Optional query parameters.

        Returns:
            The parsed JSON value (a ``dict`` or ``list`` depending on the
            endpoint).

        Raises:
            AuditError: If the request fails, the response exceeds
                :data:`MAX_RESPONSE_BYTES`, the bytes are not valid UTF-8,
                or the JSON document contains a duplicate object key. Any
                embedded token value is redacted from the raised message.
        """
        url = self._base_url + path
        if params:
            query = "&".join(f"{key}={value}" for key, value in params.items())
            url = f"{url}?{query}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": API_VERSION,
        }
        try:
            body = self._opener(url, headers)
        except AuditError as error:
            raise AuditError(self._redact(str(error))) from None
        except Exception as error:  # noqa: BLE001 - normalize every transport failure
            raise AuditError(self._redact(f"GitHub API request failed: {error}")) from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise AuditError("GitHub API response exceeded the size limit")
        try:
            text = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise AuditError(f"GitHub API response was not valid UTF-8: {error}") from None
        try:
            return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except ValueError as error:
            raise AuditError(f"GitHub API response was not valid JSON: {error}") from None

    def _redact(self, message: str) -> str:
        """Replace any literal occurrence of this client's token with ``***``."""
        return message.replace(self._token, "***")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``object_pairs_hook`` that raises on a repeated JSON object key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _build_client_from_env() -> GitHubJsonClient:
    """Build a :class:`GitHubJsonClient` from the ``GH_TOKEN`` environment variable.

    Returns:
        A client authenticated with ``GH_TOKEN``.

    Raises:
        AuditError: If ``GH_TOKEN`` is unset or empty.
    """
    token = os.environ.get("GH_TOKEN", "")
    return GitHubJsonClient(token=token)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``audit`` CLI: fetch, classify, and atomically write one report.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults
            to ``sys.argv[1:]``.

    Returns:
        ``0`` if the audit completed and found no orphan/unresolved
        records; ``1`` if it completed but found at least one
        ``orphan_active``, ``orphan_disabled``, or ``unresolved`` record
        (the report is still written so the evidence is available); ``2``
        if the arguments were invalid or the audit itself failed to
        complete (no report is written, since there is no evidence to
        publish).
    """
    parser = argparse.ArgumentParser(prog="actions_registry_audit")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--repository", required=True)
    audit_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        repository = normalize_repository(args.repository)
    except AuditError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 2

    try:
        client = _build_client_from_env()
        report = audit_actions_registry(client, repository)
    except AuditError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 2

    write_report_atomically(Path(args.output), report)

    unresolved_or_orphan = sum(
        count
        for classification, count in report["summary"].items()
        if classification in {"orphan_active", "orphan_disabled", "unresolved"}
    )
    if unresolved_or_orphan:
        print(
            f"::warning::found {unresolved_or_orphan} orphan/unresolved workflow record(s); "
            "see the written report",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI entry point
    raise SystemExit(main())
