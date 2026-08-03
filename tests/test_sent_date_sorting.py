"""Integration tests for RFC 5256 sent-date sibling sorting."""

from datetime import datetime, timezone

import pytest

from threadweave import Message, thread_messages

UTC = timezone.utc


def _message_ids(containers):
    """Return message identifiers for concrete containers in order."""
    return [
        container.message.message_id
        for container in containers
        if container.message is not None
    ]


def test_default_thread_order_remains_first_appearance_order():
    """Sent-date sorting is opt-in for backward compatibility."""
    roots = thread_messages(
        [
            Message(message_id="later", sent_date="2 Jan 2026 00:00:00 +0000"),
            Message(message_id="earlier", sent_date="1 Jan 2026 00:00:00 +0000"),
        ]
    )
    assert _message_ids(roots) == ["later", "earlier"]


def test_top_level_roots_sort_by_normalized_sent_date():
    """RFC 5256 step 4 orders top-level siblings by UTC sent date."""
    roots = thread_messages(
        [
            Message(message_id="later", sent_date="2 Jan 2026 09:00:00 +0900"),
            Message(message_id="earlier", sent_date="1 Jan 2026 23:00:00 +0000"),
        ],
        sort_by_sent_date=True,
    )
    assert _message_ids(roots) == ["earlier", "later"]


def test_equal_sent_dates_use_sequence_number_then_input_order():
    """Mailbox sequence number is the RFC tie-breaker; input order is fallback."""
    same_date = datetime(2026, 1, 1, tzinfo=UTC)
    roots = thread_messages(
        [
            Message(message_id="third", sent_date=same_date, sequence_number=4),
            Message(message_id="first", sent_date=same_date, sequence_number=1),
            Message(message_id="second", sent_date=same_date),
        ],
        sort_by_sent_date=True,
    )
    assert _message_ids(roots) == ["first", "second", "third"]


def test_missing_date_uses_internal_date_before_earliest_fallback():
    """A missing Date sorts by INTERNALDATE ahead of a later Date header."""
    roots = thread_messages(
        [
            Message(message_id="dated", sent_date="2 Jan 2026 00:00:00 +0000"),
            Message(
                message_id="internal",
                internal_date="1 Jan 2026 00:00:00 +0000",
            ),
            Message(message_id="unknown"),
        ],
        sort_by_sent_date=True,
    )
    assert _message_ids(roots) == ["unknown", "internal", "dated"]


def test_dummy_root_sorts_children_then_uses_first_child_for_root_order():
    """RFC step 4 derives a dummy root's key from its earliest sorted child."""
    roots = thread_messages(
        [
            Message(
                message_id="late-child",
                references=["missing"],
                sent_date="3 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="early-child",
                references=["missing"],
                sent_date="1 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="middle-root",
                sent_date="2 Jan 2026 00:00:00 +0000",
            ),
        ],
        sort_by_sent_date=True,
    )
    assert roots[0].message is None
    assert _message_ids(roots[0].children) == ["early-child", "late-child"]
    assert roots[1].message.message_id == "middle-root"


def test_post_subject_merge_sorts_new_sibling_set_bottom_up():
    """RFC step 6 re-sorts siblings created by subject-based thread merging."""
    roots = thread_messages(
        [
            Message(
                message_id="reply-late",
                subject="Re: Topic",
                sent_date="3 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="original",
                subject="Topic",
                sent_date="1 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="reply-middle",
                subject="Fwd: Topic",
                sent_date="2 Jan 2026 00:00:00 +0000",
            ),
        ],
        group_by_subject=True,
        sort_by_sent_date=True,
    )
    assert len(roots) == 1
    assert roots[0].message.message_id == "original"
    assert _message_ids(roots[0].children) == ["reply-middle", "reply-late"]


def test_nested_sibling_sets_sort_without_recursion():
    """Grandchildren are sorted before children and deep trees remain iterative."""
    roots = thread_messages(
        [
            Message(message_id="root", sent_date="1 Jan 2026 00:00:00 +0000"),
            Message(
                message_id="later-child",
                references=["root"],
                sent_date="3 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="earlier-child",
                references=["root"],
                sent_date="2 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="later-grandchild",
                references=["root", "earlier-child"],
                sent_date="5 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="earlier-grandchild",
                references=["root", "earlier-child"],
                sent_date="4 Jan 2026 00:00:00 +0000",
            ),
        ],
        sort_by_sent_date=True,
    )
    root = roots[0]
    assert _message_ids(root.children) == ["earlier-child", "later-child"]
    assert _message_ids(root.children[0].children) == [
        "earlier-grandchild",
        "later-grandchild",
    ]


def test_invalid_or_duplicate_explicit_sequence_numbers_are_rejected():
    """RFC sequence numbers must be unique positive integers when supplied."""
    with pytest.raises(ValueError, match="positive integer"):
        thread_messages(
            [Message(message_id="bad", sequence_number=0)],
            sort_by_sent_date=True,
        )
    with pytest.raises(ValueError, match="duplicate sequence number"):
        thread_messages(
            [
                Message(message_id="a", sequence_number=1),
                Message(message_id="b", sequence_number=1),
            ],
            sort_by_sent_date=True,
        )


def test_boolean_and_non_integer_sequence_numbers_are_rejected():
    """Booleans and numeric lookalikes are not valid mailbox sequence numbers."""
    for invalid in (True, 1.5):
        with pytest.raises(ValueError, match="positive integer"):
            thread_messages(
                [Message(message_id="bad", sequence_number=invalid)],  # type: ignore[arg-type]
                sort_by_sent_date=True,
            )


def test_message_without_id_can_be_sorted():
    """Synthetic identities do not prevent sent-date ordering."""
    roots = thread_messages(
        [
            Message(payload="later", sent_date="2 Jan 2026 00:00:00 +0000"),
            Message(payload="earlier", sent_date="1 Jan 2026 00:00:00 +0000"),
        ],
        sort_by_sent_date=True,
    )
    assert [root.message.payload for root in roots] == ["earlier", "later"]


def test_placeholder_filled_by_later_message_keeps_its_sort_metadata():
    """A later concrete message can fill a referenced dummy and sort normally."""
    roots = thread_messages(
        [
            Message(
                message_id="child",
                references=["root"],
                sent_date="2 Jan 2026 00:00:00 +0000",
            ),
            Message(
                message_id="root",
                sent_date="1 Jan 2026 00:00:00 +0000",
            ),
        ],
        sort_by_sent_date=True,
    )
    assert roots[0].message.message_id == "root"
    assert _message_ids(roots[0].children) == ["child"]
