"""Integration tests for RFC 5256 subject grouping."""

from threadweave import Message, thread_messages


def _thread_message_ids(root) -> set[str]:
    """Return every message identifier in one thread tree."""
    nodes = [root, *root.iter_descendants()]
    return {
        node.message.message_id
        for node in nodes
        if node.message is not None
    }


def test_subject_grouping_uses_blobs_and_forward_detection():
    """List blobs and forward artifacts merge under the original root."""
    original = Message(message_id="original", subject="[project] Topic")
    forwarded = Message(message_id="forwarded", subject="[project] Fwd: Topic")

    grouped = thread_messages(
        [forwarded, original],
        group_by_subject=True,
    )

    assert len(grouped) == 1
    assert grouped[0].message.message_id == "original"
    assert _thread_message_ids(grouped[0]) == {"original", "forwarded"}


def test_subject_grouping_decodes_encoded_words_before_comparison():
    """Encoded and decoded representations share one RFC 5256 base subject."""
    grouped = thread_messages(
        [
            Message(message_id="original", subject="안녕"),
            Message(
                message_id="reply",
                subject="=?utf-8?q?Re=3A_=EC=95=88=EB=85=95?=",
            ),
        ],
        group_by_subject=True,
    )

    assert len(grouped) == 1
    assert _thread_message_ids(grouped[0]) == {"original", "reply"}
