"""Contract tests for the read-only GitHub Actions registry lifecycle auditor.

These tests never perform real network I/O. Every GitHub API interaction is
driven through an injected fetch function so the suite stays deterministic
and credential-free, matching ADR-0005's automation-authority boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import actions_registry_audit as audit


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "actions_registry_audit.py"


def test_actions_registry_audit_production_module_exists() -> None:
    """The fleet incident needs an executable repository-owned detector."""

    assert MODULE_PATH.is_file(), "scripts/ci/actions_registry_audit.py is not implemented"


# ---------------------------------------------------------------------------
# Identity normalization
# ---------------------------------------------------------------------------


class TestNormalizeRepository:
    """`normalize_repository` accepts only canonical `owner/name` text."""

    def test_accepts_canonical_owner_name(self) -> None:
        assert audit.normalize_repository("ContextualWisdomLab/ThreadWeave") == (
            "ContextualWisdomLab/ThreadWeave"
        )

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "ThreadWeave",
            "ContextualWisdomLab/ThreadWeave/extra",
            "/ThreadWeave",
            "ContextualWisdomLab/",
            "Contextual Wisdom/ThreadWeave",
            "ContextualWisdomLab/Thread\nWeave",
            123,  # type: ignore[arg-type]
        ],
    )
    def test_rejects_malformed_repository(self, value: object) -> None:
        with pytest.raises(audit.AuditError):
            audit.normalize_repository(value)  # type: ignore[arg-type]


class TestNormalizeSha:
    """`normalize_sha` accepts only exact lowercase 40-hex identities."""

    def test_accepts_lowercase_forty_hex(self) -> None:
        sha = "a" * 40
        assert audit.normalize_sha(sha, label="head") == sha

    @pytest.mark.parametrize(
        "value",
        [
            "A" * 40,  # uppercase
            "a" * 39,  # too short
            "a" * 41,  # too long
            "g" * 40,  # non-hex
            "",
            None,
            42,
        ],
    )
    def test_rejects_malformed_sha(self, value: object) -> None:
        with pytest.raises(audit.AuditError):
            audit.normalize_sha(value, label="head")  # type: ignore[arg-type]


class TestNormalizeWorkflowPath:
    """`normalize_workflow_path` accepts only exact repository workflow paths."""

    @pytest.mark.parametrize(
        "value",
        [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yaml",
            ".github/workflows/a.yml",
        ],
    )
    def test_accepts_exact_workflow_paths(self, value: str) -> None:
        assert audit.normalize_workflow_path(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "workflows/ci.yml",
            ".github/workflows/",
            ".github/workflows/../ci.yml",
            ".github//workflows/ci.yml",
            ".github/workflows/ci.yml/",
            ".github\\workflows\\ci.yml",
            ".github/workflows/ci.txt",
            ".github/workflows/ci.yml\x00",
            "dynamic/workflow",
            None,
            7,
        ],
    )
    def test_rejects_malformed_workflow_path(self, value: object) -> None:
        with pytest.raises(audit.AuditError):
            audit.normalize_workflow_path(value)  # type: ignore[arg-type]

    def test_rejects_non_nfc_path(self) -> None:
        # "e" + combining acute accent (NFD) instead of the precomposed
        # "é" (NFC); both render identically but must not silently collapse.
        nfd_path = ".github/workflows/café.yml"
        with pytest.raises(audit.AuditError):
            audit.normalize_workflow_path(nfd_path)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _record(id_: int, name: str, path: str, state: str) -> dict:
    return {"id": id_, "name": name, "path": path, "state": state}


class TestClassifyWorkflowRecords:
    """Every registry record receives exactly one finite classification."""

    def test_present_active_backed_by_protected_main(self) -> None:
        records = [_record(1, "CI", ".github/workflows/ci.yml", "active")]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "present_active"

    def test_present_disabled_backed_by_protected_main(self) -> None:
        records = [
            _record(1, "CI", ".github/workflows/ci.yml", "disabled_manually")
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "present_disabled"

    def test_active_pr_workflow_absent_from_main_present_on_pr_head(self) -> None:
        records = [
            _record(2, "PR20 repair", ".github/workflows/apply-pr20.yml", "active")
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths={".github/workflows/apply-pr20.yml"},
        )
        assert result[0].classification == "active_pr_workflow"

    def test_orphan_active_absent_from_main_and_every_pr_head(self) -> None:
        records = [
            _record(3, "apply-pr20-concurrency-fix", ".github/workflows/apply-pr20-concurrency-fix.yml", "active")
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "orphan_active"
        assert result[0].workflow_id in {r.workflow_id for r in result if r.classification == "orphan_active"}

    def test_orphan_disabled_absent_from_main_and_pr_heads(self) -> None:
        records = [
            _record(4, "bootstrap-ci-lock", ".github/workflows/bootstrap-ci-lock.yml", "disabled_manually")
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "orphan_disabled"

    def test_dynamic_owned_for_non_repository_path(self) -> None:
        records = [_record(5, "Dynamic workflow", "dynamic/38553635", "active")]
        result = audit.classify_workflow_records(
            records,
            protected_paths=set(),
            active_pr_paths=set(),
        )
        assert result[0].classification == "dynamic_owned"

    def test_unresolved_for_malformed_record(self) -> None:
        records = [{"id": 6, "name": "broken"}]  # missing path/state
        result = audit.classify_workflow_records(
            records,
            protected_paths=set(),
            active_pr_paths=set(),
        )
        assert result[0].classification == "unresolved"

    def test_unresolved_for_duplicate_workflow_id(self) -> None:
        records = [
            _record(7, "CI", ".github/workflows/ci.yml", "active"),
            _record(7, "CI duplicate", ".github/workflows/other.yml", "active"),
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml", ".github/workflows/other.yml"},
            active_pr_paths=set(),
        )
        assert all(r.classification == "unresolved" for r in result)

    def test_unresolved_for_non_positive_workflow_id(self) -> None:
        records = [_record(0, "CI", ".github/workflows/ci.yml", "active")]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "unresolved"

    def test_unresolved_for_boolean_workflow_id(self) -> None:
        records = [_record(True, "CI", ".github/workflows/ci.yml", "active")]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "unresolved"

    def test_only_orphan_active_appears_in_recommended_disable_ids(self) -> None:
        records = [
            _record(1, "CI", ".github/workflows/ci.yml", "active"),
            _record(2, "orphan", ".github/workflows/apply-pr20-x.yml", "active"),
            _record(3, "orphan-disabled", ".github/workflows/apply-pr20-y.yml", "disabled_manually"),
        ]
        result = audit.classify_workflow_records(
            records,
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        recommended = audit.recommended_disable_workflow_ids(result)
        assert recommended == [2]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class _FakePaginatedClient:
    """Deterministic byte-level fake of `GitHubJsonClient.get` for pagination tests."""

    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages
        self.calls: list[dict] = []

    def get(self, path: str, *, params: dict | None = None) -> dict:
        self.calls.append({"path": path, "params": dict(params or {})})
        page_number = int((params or {}).get("page", 1))
        index = page_number - 1
        if index < 0 or index >= len(self._pages):
            return {"total_count": self._pages[0].get("total_count", 0), "workflows": []}
        return self._pages[index]


class TestListWorkflowRecords:
    """`list_workflow_records` performs complete, bounded, verified pagination."""

    def test_single_page_under_per_page_limit(self) -> None:
        client = _FakePaginatedClient(
            [{"total_count": 1, "workflows": [_record(1, "CI", ".github/workflows/ci.yml", "active")]}]
        )
        records, receipts = audit.list_workflow_records(client, "ContextualWisdomLab/ThreadWeave")
        assert len(records) == 1
        assert receipts.pages_fetched == 1
        assert receipts.total_count == 1

    def test_multiple_full_pages_are_all_fetched(self) -> None:
        per_page = audit.WORKFLOWS_PER_PAGE
        first_page = [
            _record(i, f"wf-{i}", f".github/workflows/wf-{i}.yml", "active")
            for i in range(1, per_page + 1)
        ]
        second_page = [_record(per_page + 1, "last", ".github/workflows/last.yml", "active")]
        client = _FakePaginatedClient(
            [
                {"total_count": per_page + 1, "workflows": first_page},
                {"total_count": per_page + 1, "workflows": second_page},
            ]
        )
        records, receipts = audit.list_workflow_records(client, "ContextualWisdomLab/ThreadWeave")
        assert len(records) == per_page + 1
        assert receipts.pages_fetched == 2

    def test_total_count_mismatch_fails_closed(self) -> None:
        client = _FakePaginatedClient(
            [{"total_count": 5, "workflows": [_record(1, "CI", ".github/workflows/ci.yml", "active")]}]
        )
        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(client, "ContextualWisdomLab/ThreadWeave")

    def test_repeated_page_fails_closed(self) -> None:
        per_page = audit.WORKFLOWS_PER_PAGE
        full_page = [
            _record(i, f"wf-{i}", f".github/workflows/wf-{i}.yml", "active")
            for i in range(1, per_page + 1)
        ]

        class _RepeatingClient:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"total_count": per_page * 3, "workflows": full_page}

        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(_RepeatingClient(), "ContextualWisdomLab/ThreadWeave")

    def test_page_cap_fails_closed(self) -> None:
        per_page = audit.WORKFLOWS_PER_PAGE

        class _UnboundedClient:
            def __init__(self) -> None:
                self.page = 0

            def get(self, path: str, *, params: dict | None = None) -> dict:
                self.page += 1
                records = [
                    _record(
                        self.page * per_page + i,
                        f"wf-{self.page}-{i}",
                        f".github/workflows/wf-{self.page}-{i}.yml",
                        "active",
                    )
                    for i in range(per_page)
                ]
                return {"total_count": 10**9, "workflows": records}

        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(_UnboundedClient(), "ContextualWisdomLab/ThreadWeave")

    def test_malformed_page_fails_closed(self) -> None:
        client = _FakePaginatedClient([{"total_count": 1, "workflows": "not-a-list"}])
        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(client, "ContextualWisdomLab/ThreadWeave")


class TestListOpenPullRequests:
    """`list_open_pull_requests` binds only same-repository PR heads."""

    def test_returns_same_repository_open_pull_requests(self) -> None:
        pulls_page = [
            {
                "number": 20,
                "head": {"sha": "b" * 40, "repo": {"full_name": "ContextualWisdomLab/ThreadWeave"}},
                "base": {"sha": "c" * 40},
            }
        ]

        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict | list:
                page = int((params or {}).get("page", 1))
                return pulls_page if page == 1 else []

        result, receipts = audit.list_open_pull_requests(
            _Client(), "ContextualWisdomLab/ThreadWeave"
        )
        assert len(result) == 1
        assert result[0].number == 20
        assert result[0].head_sha == "b" * 40
        assert receipts.pages_fetched == 1

    def test_excludes_fork_pull_requests(self) -> None:
        pulls_page = [
            {
                "number": 21,
                "head": {"sha": "d" * 40, "repo": {"full_name": "someone-else/ThreadWeave"}},
                "base": {"sha": "c" * 40},
            }
        ]

        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict | list:
                page = int((params or {}).get("page", 1))
                return pulls_page if page == 1 else []

        result, _receipts = audit.list_open_pull_requests(
            _Client(), "ContextualWisdomLab/ThreadWeave"
        )
        assert result == []

    def test_excludes_pull_request_with_null_head_repo(self) -> None:
        """A deleted fork/head repository reports `head.repo: null`; exclude it."""

        pulls_page = [
            {
                "number": 22,
                "head": {"sha": "e" * 40, "repo": None},
                "base": {"sha": "c" * 40},
            }
        ]

        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict | list:
                page = int((params or {}).get("page", 1))
                return pulls_page if page == 1 else []

        result, _receipts = audit.list_open_pull_requests(
            _Client(), "ContextualWisdomLab/ThreadWeave"
        )
        assert result == []

    def test_malformed_pull_request_head_fails_closed(self) -> None:
        pulls_page = [{"number": 23, "head": {"sha": "not-a-sha"}, "base": {}}]

        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict | list:
                page = int((params or {}).get("page", 1))
                return pulls_page if page == 1 else []

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_Client(), "ContextualWisdomLab/ThreadWeave")


class TestWorkflowPathsFromTree:
    """`workflow_paths_from_tree` extracts exact `.github/workflows/*` blobs."""

    def test_extracts_workflow_blob_paths(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {
                    "sha": "f" * 40,
                    "truncated": False,
                    "tree": [
                        {"path": ".github/workflows/ci.yml", "type": "blob"},
                        {"path": ".github/workflows", "type": "tree"},
                        {"path": "README.md", "type": "blob"},
                    ],
                }

        paths = audit.workflow_paths_from_tree(
            _Client(), "ContextualWisdomLab/ThreadWeave", "f" * 40
        )
        assert paths == {".github/workflows/ci.yml"}

    def test_truncated_tree_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"sha": "f" * 40, "truncated": True, "tree": []}

        with pytest.raises(audit.AuditError):
            audit.workflow_paths_from_tree(
                _Client(), "ContextualWisdomLab/ThreadWeave", "f" * 40
            )

    def test_malformed_tree_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"sha": "f" * 40, "truncated": False, "tree": "nope"}

        with pytest.raises(audit.AuditError):
            audit.workflow_paths_from_tree(
                _Client(), "ContextualWisdomLab/ThreadWeave", "f" * 40
            )

    def test_ignores_malformed_individual_workflow_path(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {
                    "sha": "f" * 40,
                    "truncated": False,
                    "tree": [
                        {"path": ".github/workflows/ci.yml", "type": "blob"},
                        {"path": ".github/workflows/../escape.yml", "type": "blob"},
                    ],
                }

        paths = audit.workflow_paths_from_tree(
            _Client(), "ContextualWisdomLab/ThreadWeave", "f" * 40
        )
        assert paths == {".github/workflows/ci.yml"}


# ---------------------------------------------------------------------------
# End-to-end audit and evidence report
# ---------------------------------------------------------------------------


class _StubClient:
    """Full injected client covering every endpoint `audit_actions_registry` calls."""

    def __init__(
        self,
        *,
        default_branch_sha: str,
        workflow_records: list[dict],
        pull_requests: list[dict],
        main_tree: dict,
        pr_trees: dict[str, dict] | None = None,
        drift_default_branch_sha: str | None = None,
    ) -> None:
        self.default_branch_sha = default_branch_sha
        self.workflow_records = workflow_records
        self.pull_requests = pull_requests
        self.main_tree = main_tree
        self.pr_trees = pr_trees or {}
        self._drift_default_branch_sha = drift_default_branch_sha
        self._branch_calls = 0

    def get(self, path: str, *, params: dict | None = None) -> dict | list:
        params = params or {}
        if path.endswith("/branches/main"):
            self._branch_calls += 1
            if self._branch_calls > 1 and self._drift_default_branch_sha:
                return {"commit": {"sha": self._drift_default_branch_sha}}
            return {"commit": {"sha": self.default_branch_sha}}
        if path.endswith("/actions/workflows"):
            page = int(params.get("page", 1))
            if page == 1:
                return {"total_count": len(self.workflow_records), "workflows": self.workflow_records}
            return {"total_count": len(self.workflow_records), "workflows": []}
        if path.endswith("/pulls"):
            page = int(params.get("page", 1))
            return self.pull_requests if page == 1 else []
        if "/git/trees/" in path:
            sha = path.rsplit("/", 1)[-1]
            if sha == self.default_branch_sha:
                return self.main_tree
            return self.pr_trees.get(sha, {"sha": sha, "truncated": False, "tree": []})
        raise AssertionError(f"unexpected path: {path}")


def _base_stub_client(**overrides: object) -> _StubClient:
    defaults = dict(
        default_branch_sha="a" * 40,
        workflow_records=[_record(1, "CI", ".github/workflows/ci.yml", "active")],
        pull_requests=[],
        main_tree={
            "sha": "a" * 40,
            "truncated": False,
            "tree": [{"path": ".github/workflows/ci.yml", "type": "blob"}],
        },
    )
    defaults.update(overrides)
    return _StubClient(**defaults)  # type: ignore[arg-type]


class TestAuditActionsRegistry:
    """`audit_actions_registry` produces one deterministic schema-v1 report."""

    def test_reports_present_active_for_protected_workflow(self) -> None:
        client = _base_stub_client()
        report = audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")
        assert report["schema"] == "threadweave.actions-registry-audit/v1"
        assert report["repository"] == "ContextualWisdomLab/ThreadWeave"
        assert report["protected_main_sha"] == "a" * 40
        [record] = report["records"]
        assert record["classification"] == "present_active"
        assert report["summary"]["present_active"] == 1
        assert report["recommended_disable_workflow_ids"] == []

    def test_reports_confirmed_orphan_active(self) -> None:
        client = _base_stub_client(
            workflow_records=[
                _record(1, "CI", ".github/workflows/ci.yml", "active"),
                _record(2, "orphan", ".github/workflows/apply-pr20-x.yml", "active"),
            ]
        )
        report = audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")
        assert report["summary"]["orphan_active"] == 1
        assert report["recommended_disable_workflow_ids"] == [2]

    def test_active_pr_workflow_excluded_from_orphans(self) -> None:
        pr_head = "b" * 40
        client = _base_stub_client(
            workflow_records=[
                _record(1, "CI", ".github/workflows/ci.yml", "active"),
                _record(2, "pr20-repair", ".github/workflows/apply-pr20.yml", "active"),
            ],
            pull_requests=[
                {
                    "number": 20,
                    "head": {"sha": pr_head, "repo": {"full_name": "ContextualWisdomLab/ThreadWeave"}},
                    "base": {"sha": "a" * 40},
                }
            ],
            pr_trees={
                pr_head: {
                    "sha": pr_head,
                    "truncated": False,
                    "tree": [
                        {"path": ".github/workflows/ci.yml", "type": "blob"},
                        {"path": ".github/workflows/apply-pr20.yml", "type": "blob"},
                    ],
                }
            },
        )
        report = audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")
        assert report["summary"].get("orphan_active", 0) == 0
        assert report["summary"]["active_pr_workflow"] == 1
        assert report["recommended_disable_workflow_ids"] == []

    def test_default_branch_drift_fails_closed(self) -> None:
        client = _base_stub_client(drift_default_branch_sha="c" * 40)
        with pytest.raises(audit.AuditError):
            audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")

    def test_report_excludes_secret_shaped_and_uncontrolled_fields(self) -> None:
        client = _base_stub_client()
        report = audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")
        encoded = json.dumps(report)
        assert "token" not in encoded.lower()
        assert "authorization" not in encoded.lower()

    def test_deterministic_ordering_by_workflow_id(self) -> None:
        client = _base_stub_client(
            workflow_records=[
                _record(9, "z", ".github/workflows/apply-z.yml", "active"),
                _record(2, "a", ".github/workflows/apply-a.yml", "active"),
            ]
        )
        report = audit.audit_actions_registry(client, "ContextualWisdomLab/ThreadWeave")
        ids = [r["workflow_id"] for r in report["records"]]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Report encoding / atomic write
# ---------------------------------------------------------------------------


class TestEncodeAndWriteReport:
    def test_encode_report_is_deterministic_and_sorted(self) -> None:
        report = {"b": 1, "a": 2}
        first = audit.encode_report(report)
        second = audit.encode_report(report)
        assert first == second
        assert first.index(b'"a"') < first.index(b'"b"')

    def test_write_report_atomically_creates_final_file(self, tmp_path: Path) -> None:
        target = tmp_path / "report.json"
        audit.write_report_atomically(target, {"schema": "threadweave.actions-registry-audit/v1"})
        assert target.is_file()
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["schema"] == "threadweave.actions-registry-audit/v1"

    def test_write_report_atomically_leaves_no_temp_file_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "report.json"
        audit.write_report_atomically(target, {"schema": "threadweave.actions-registry-audit/v1"})
        leftovers = [p for p in tmp_path.iterdir() if p != target]
        assert leftovers == []


# ---------------------------------------------------------------------------
# GitHubJsonClient
# ---------------------------------------------------------------------------


class TestGitHubJsonClient:
    def test_get_parses_json_response(self) -> None:
        def fake_opener(url: str, headers: dict) -> bytes:
            assert headers["Accept"] == "application/vnd.github+json"
            assert headers["X-GitHub-Api-Version"] == audit.API_VERSION
            assert "Authorization" in headers
            return b'{"total_count": 1, "workflows": []}'

        client = audit.GitHubJsonClient(token="ghp_fake", opener=fake_opener)
        result = client.get("/repos/ContextualWisdomLab/ThreadWeave/actions/workflows")
        assert result == {"total_count": 1, "workflows": []}

    def test_get_rejects_duplicate_json_keys(self) -> None:
        def fake_opener(url: str, headers: dict) -> bytes:
            return b'{"a": 1, "a": 2}'

        client = audit.GitHubJsonClient(token="ghp_fake", opener=fake_opener)
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")

    def test_get_rejects_invalid_utf8(self) -> None:
        def fake_opener(url: str, headers: dict) -> bytes:
            return b"\xff\xfe not utf-8"

        client = audit.GitHubJsonClient(token="ghp_fake", opener=fake_opener)
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")

    def test_get_rejects_oversized_response(self) -> None:
        def fake_opener(url: str, headers: dict) -> bytes:
            return b"[" + b"1," * (audit.MAX_RESPONSE_BYTES) + b"1]"

        client = audit.GitHubJsonClient(token="ghp_fake", opener=fake_opener)
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")

    def test_get_wraps_http_error(self) -> None:
        def failing_opener(url: str, headers: dict) -> bytes:
            raise audit.HttpStatusError(url=url, status=404)

        client = audit.GitHubJsonClient(token="ghp_fake", opener=failing_opener)
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")

    def test_get_redacts_token_from_diagnostics(self) -> None:
        secret = "ghp_super_secret_value"

        def failing_opener(url: str, headers: dict) -> bytes:
            raise audit.HttpStatusError(url=url, status=500)

        client = audit.GitHubJsonClient(token=secret, opener=failing_opener)
        with pytest.raises(audit.AuditError) as excinfo:
            client.get("/repos/x/y")
        assert secret not in str(excinfo.value)

    def test_missing_token_raises(self) -> None:
        with pytest.raises(audit.AuditError):
            audit.GitHubJsonClient(token="", opener=lambda url, headers: b"{}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_writes_report_and_exits_zero_when_clean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        output = tmp_path / "report.json"
        client = _base_stub_client()
        monkeypatch.setattr(audit, "_build_client_from_env", lambda: client)
        exit_code = audit.main(
            [
                "audit",
                "--repository",
                "ContextualWisdomLab/ThreadWeave",
                "--output",
                str(output),
            ]
        )
        assert exit_code == 0
        assert output.is_file()

    def test_main_exits_nonzero_and_still_writes_report_on_orphan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = tmp_path / "report.json"
        client = _base_stub_client(
            workflow_records=[
                _record(1, "CI", ".github/workflows/ci.yml", "active"),
                _record(2, "orphan", ".github/workflows/apply-pr20-x.yml", "active"),
            ]
        )
        monkeypatch.setattr(audit, "_build_client_from_env", lambda: client)
        exit_code = audit.main(
            [
                "audit",
                "--repository",
                "ContextualWisdomLab/ThreadWeave",
                "--output",
                str(output),
            ]
        )
        assert exit_code == 1
        assert output.is_file()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["summary"]["orphan_active"] == 1

    def test_main_exits_nonzero_without_writing_report_on_audit_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = tmp_path / "report.json"

        class _FailingClient:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                raise audit.AuditError("boom")

        monkeypatch.setattr(audit, "_build_client_from_env", lambda: _FailingClient())
        exit_code = audit.main(
            [
                "audit",
                "--repository",
                "ContextualWisdomLab/ThreadWeave",
                "--output",
                str(output),
            ]
        )
        assert exit_code == 2
        assert not output.exists()

    def test_main_rejects_malformed_repository_argument(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        exit_code = audit.main(
            ["audit", "--repository", "not-a-repo", "--output", str(output)]
        )
        assert exit_code == 2
        assert not output.exists()


# ---------------------------------------------------------------------------
# Additional branch coverage: malformed shapes not already exercised above
# ---------------------------------------------------------------------------


class TestClassifyWorkflowRecordsMalformedInput:
    def test_non_mapping_record_is_unresolved(self) -> None:
        result = audit.classify_workflow_records(
            ["not-a-mapping"], protected_paths=set(), active_pr_paths=set()
        )
        assert result[0].classification == "unresolved"
        assert result[0].reason == "not an object"

    def test_record_missing_id_key_is_unresolved(self) -> None:
        result = audit.classify_workflow_records(
            [{"name": "CI", "path": ".github/workflows/ci.yml", "state": "active"}],
            protected_paths={".github/workflows/ci.yml"},
            active_pr_paths=set(),
        )
        assert result[0].classification == "unresolved"


class TestListWorkflowRecordsMalformedInput:
    def test_non_mapping_response_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return ["not-a-mapping"]

        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_non_integer_total_count_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"total_count": "one", "workflows": []}

        with pytest.raises(audit.AuditError):
            audit.list_workflow_records(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_empty_first_page_returns_no_records(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"total_count": 0, "workflows": []}

        records, receipts = audit.list_workflow_records(
            _Client(), "ContextualWisdomLab/ThreadWeave"
        )
        assert records == []
        assert receipts.pages_fetched == 1


class TestListOpenPullRequestsMalformedInput:
    def test_page_cap_fails_closed(self) -> None:
        class _UnboundedClient:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return [
                    {
                        "number": i,
                        "head": {"sha": "a" * 40, "repo": {"full_name": "ContextualWisdomLab/ThreadWeave"}},
                        "base": {},
                    }
                    for i in range(audit.PULLS_PER_PAGE)
                ]

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_UnboundedClient(), "ContextualWisdomLab/ThreadWeave")

    def test_non_list_response_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> dict:
                return {"not": "a list"}

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_non_mapping_entry_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return ["not-a-mapping"]

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_non_mapping_head_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return [{"number": 1, "head": "not-a-mapping", "base": {}}]

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_non_mapping_head_repo_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return [{"number": 1, "head": {"sha": "a" * 40, "repo": "not-a-mapping"}, "base": {}}]

        with pytest.raises(audit.AuditError):
            audit.list_open_pull_requests(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_multiple_full_pages_are_all_fetched(self) -> None:
        per_page = audit.PULLS_PER_PAGE
        first_page = [
            {
                "number": i,
                "head": {"sha": f"{i:040x}", "repo": {"full_name": "ContextualWisdomLab/ThreadWeave"}},
                "base": {},
            }
            for i in range(1, per_page + 1)
        ]
        second_page = [
            {
                "number": per_page + 1,
                "head": {"sha": "b" * 40, "repo": {"full_name": "ContextualWisdomLab/ThreadWeave"}},
                "base": {},
            }
        ]

        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                page = int((params or {}).get("page", 1))
                return first_page if page == 1 else second_page

        pulls, receipts = audit.list_open_pull_requests(
            _Client(), "ContextualWisdomLab/ThreadWeave"
        )
        assert len(pulls) == per_page + 1
        assert receipts.pages_fetched == 2


class TestWorkflowPathsFromTreeMalformedInput:
    def test_non_mapping_response_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None) -> list:
                return ["not-a-mapping"]

        with pytest.raises(audit.AuditError):
            audit.workflow_paths_from_tree(_Client(), "ContextualWisdomLab/ThreadWeave", "f" * 40)


class TestAuditActionsRegistryMalformedBranch:
    def test_initial_branch_response_not_mapping_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None):
                if path.endswith("/branches/main"):
                    return ["not-a-mapping"]
                raise AssertionError(f"unexpected path: {path}")

        with pytest.raises(audit.AuditError):
            audit.audit_actions_registry(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_initial_branch_commit_not_mapping_fails_closed(self) -> None:
        class _Client:
            def get(self, path: str, *, params: dict | None = None):
                if path.endswith("/branches/main"):
                    return {"commit": "not-a-mapping"}
                raise AssertionError(f"unexpected path: {path}")

        with pytest.raises(audit.AuditError):
            audit.audit_actions_registry(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_revalidation_branch_response_not_mapping_fails_closed(self) -> None:
        default_branch_sha = "a" * 40
        call_count = {"branch": 0}

        class _Client:
            def get(self, path: str, *, params: dict | None = None):
                params = params or {}
                if path.endswith("/branches/main"):
                    call_count["branch"] += 1
                    if call_count["branch"] > 1:
                        return ["not-a-mapping"]
                    return {"commit": {"sha": default_branch_sha}}
                if path.endswith("/actions/workflows"):
                    return {"total_count": 0, "workflows": []}
                if path.endswith("/pulls"):
                    return []
                if "/git/trees/" in path:
                    return {"sha": default_branch_sha, "truncated": False, "tree": []}
                raise AssertionError(f"unexpected path: {path}")

        with pytest.raises(audit.AuditError):
            audit.audit_actions_registry(_Client(), "ContextualWisdomLab/ThreadWeave")

    def test_revalidation_branch_commit_not_mapping_fails_closed(self) -> None:
        default_branch_sha = "a" * 40
        call_count = {"branch": 0}

        class _Client:
            def get(self, path: str, *, params: dict | None = None):
                params = params or {}
                if path.endswith("/branches/main"):
                    call_count["branch"] += 1
                    if call_count["branch"] > 1:
                        return {"commit": "not-a-mapping"}
                    return {"commit": {"sha": default_branch_sha}}
                if path.endswith("/actions/workflows"):
                    return {"total_count": 0, "workflows": []}
                if path.endswith("/pulls"):
                    return []
                if "/git/trees/" in path:
                    return {"sha": default_branch_sha, "truncated": False, "tree": []}
                raise AssertionError(f"unexpected path: {path}")

        with pytest.raises(audit.AuditError):
            audit.audit_actions_registry(_Client(), "ContextualWisdomLab/ThreadWeave")


class TestWriteReportAtomicallyFailure:
    def test_write_failure_cleans_up_temp_file_and_reraises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "report.json"

        def _boom(*_args: object, **_kwargs: object):
            raise OSError("disk full")

        monkeypatch.setattr(audit.os, "replace", _boom)
        with pytest.raises(OSError):
            audit.write_report_atomically(target, {"schema": audit.REPORT_SCHEMA})
        leftovers = list(tmp_path.iterdir())
        assert leftovers == []


class TestGitHubJsonClientTransport:
    def test_get_includes_query_string_for_params(self) -> None:
        captured: dict[str, str] = {}

        def fake_opener(url: str, headers: dict) -> bytes:
            captured["url"] = url
            return b"{}"

        client = audit.GitHubJsonClient(token="ghp_fake", opener=fake_opener)
        client.get("/repos/x/y/pulls", params={"state": "open", "page": 1})
        assert "state=open" in captured["url"]
        assert "page=1" in captured["url"]

    def test_get_wraps_unexpected_exception(self) -> None:
        def failing_opener(url: str, headers: dict) -> bytes:
            raise RuntimeError("connection reset")

        client = audit.GitHubJsonClient(token="ghp_fake", opener=failing_opener)
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")

    def test_default_opener_parses_a_real_urlopen_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import io

        class _FakeResponse(io.BytesIO):
            def __enter__(self) -> "_FakeResponse":
                return self

            def __exit__(self, *exc_info: object) -> None:
                self.close()

        def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
            return _FakeResponse(b'{"total_count": 0, "workflows": []}')

        monkeypatch.setattr(audit.urllib.request, "urlopen", fake_urlopen)
        client = audit.GitHubJsonClient(token="ghp_fake")
        result = client.get("/repos/ContextualWisdomLab/ThreadWeave/actions/workflows")
        assert result == {"total_count": 0, "workflows": []}

    def test_default_opener_wraps_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        def fake_urlopen(request: object, timeout: float):
            raise urllib.error.HTTPError("https://api.github.com/x", 404, "Not Found", {}, None)

        monkeypatch.setattr(audit.urllib.request, "urlopen", fake_urlopen)
        client = audit.GitHubJsonClient(token="ghp_fake")
        with pytest.raises(audit.AuditError):
            client.get("/repos/x/y")


class TestBuildClientFromEnv:
    def test_builds_client_from_gh_token_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GH_TOKEN", "ghp_from_env")
        client = audit._build_client_from_env()
        assert isinstance(client, audit.GitHubJsonClient)
        assert client._token == "ghp_from_env"

    def test_missing_gh_token_env_var_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with pytest.raises(audit.AuditError):
            audit._build_client_from_env()
