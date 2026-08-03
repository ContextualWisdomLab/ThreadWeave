"""Tests for the JWZ threading assembly.

Assertions target thread *count* and co-threading *membership* (both
shape-independent, so they catch real bugs regardless of exactly where a
container lands in the tree), plus ancestor relationships for simple chains.
"""

from threadweave import Container, Message, thread_messages


def _ids(container: Container) -> set[str]:
    """Every message-id present in the thread rooted at ``container``."""
    found: set[str] = set()
    if container.message is not None:
        found.add(container.message.message_id)
    for descendant in container.iter_descendants():
        if descendant.message is not None:
            found.add(descendant.message.message_id)
    return found


def _find(roots, message_id) -> Container:
    """Locate the container whose message has ``message_id``."""
    for root in roots:
        for node in [root, *root.iter_descendants()]:
            if node.message is not None and node.message.message_id == message_id:
                return node
    raise AssertionError(f"no container for {message_id!r}")


def _is_ancestor(roots, ancestor_id, descendant_id) -> bool:
    """Return whether one message container is an ancestor of another."""
    node = _find(roots, ancestor_id)
    return any(
        descendant.message is not None
        and descendant.message.message_id == descendant_id
        for descendant in node.iter_descendants()
    )


def test_linear_chain():
    threads = thread_messages(
        [
            Message(message_id="a"),
            Message(message_id="b", in_reply_to="a", references=["a"]),
            Message(message_id="c", references=["a", "b"]),
        ]
    )
    assert len(threads) == 1
    assert _ids(threads[0]) == {"a", "b", "c"}
    assert _is_ancestor(threads, "a", "b")
    assert _is_ancestor(threads, "b", "c")


def test_two_independents():
    threads = thread_messages([Message(message_id="x"), Message(message_id="y")])
    assert len(threads) == 2
    assert {frozenset(_ids(thread)) for thread in threads} == {
        frozenset({"x"}),
        frozenset({"y"}),
    }


def test_missing_root_becomes_placeholder():
    threads = thread_messages(
        [
            Message(message_id="b", references=["a"]),
            Message(message_id="c", references=["a", "b"]),
        ]
    )
    assert len(threads) == 1
    assert _ids(threads[0]) == {"b", "c"}
    assert _is_ancestor(threads, "b", "c")


def test_fork():
    threads = thread_messages(
        [
            Message(message_id="a"),
            Message(message_id="b", references=["a"]),
            Message(message_id="c", references=["a"]),
        ]
    )
    assert len(threads) == 1
    assert _ids(threads[0]) == {"a", "b", "c"}
    assert _is_ancestor(threads, "a", "b")
    assert _is_ancestor(threads, "a", "c")


def test_subject_grouping_toggle():
    messages = [
        Message(message_id="p", subject="Hello"),
        Message(message_id="q", subject="Re: Hello"),
    ]
    grouped = thread_messages(messages, group_by_subject=True)
    assert len(grouped) == 1
    assert _ids(grouped[0]) == {"p", "q"}

    ungrouped = thread_messages(messages, group_by_subject=False)
    assert len(ungrouped) == 2


def test_self_reference_terminates():
    threads = thread_messages([Message(message_id="a", references=["a"])])
    assert len(threads) == 1
    assert _ids(threads[0]) == {"a"}


def test_mutual_reference_terminates():
    threads = thread_messages(
        [
            Message(message_id="a", references=["b"]),
            Message(message_id="b", references=["a"]),
        ]
    )
    assert len(threads) == 1
    assert _ids(threads[0]) == {"a", "b"}


def test_duplicate_message_ids_not_destructive():
    threads = thread_messages(
        [
            Message(message_id="dup", subject="first", payload=1),
            Message(message_id="dup", subject="second", payload=2),
        ]
    )
    payloads = {
        node.message.payload
        for thread in threads
        for node in [thread, *thread.iter_descendants()]
        if node.message is not None
    }
    assert payloads == {1, 2}


def test_returns_containers():
    threads = thread_messages([Message(message_id="a")])
    assert all(isinstance(thread, Container) for thread in threads)
    assert threads[0].parent is None


def test_deep_linear_chain_does_not_recurse():
    n = 3000
    messages = [Message(message_id="m0")]
    for index in range(1, n):
        parent = f"m{index - 1}"
        messages.append(
            Message(
                message_id=f"m{index}",
                in_reply_to=parent,
                references=[parent],
            )
        )
    threads = thread_messages(messages)
    assert len(threads) == 1
    assert len(_ids(threads[0])) == n
    assert _is_ancestor(threads, "m0", f"m{n - 1}")


def test_subject_grouping_is_case_insensitive():
    grouped = thread_messages(
        [
            Message(message_id="p", subject="Weekly Report"),
            Message(message_id="q", subject="re: WEEKLY REPORT"),
        ],
        group_by_subject=True,
    )
    assert len(grouped) == 1
    assert _ids(grouped[0]) == {"p", "q"}


def test_subject_grouping_preserves_first_appearance_order():
    grouped = thread_messages(
        [
            Message(message_id="a", subject="Shared"),
            Message(message_id="b", subject="Shared"),
            Message(message_id="c", subject="Later"),
        ],
        group_by_subject=True,
    )

    assert [_ids(thread) for thread in grouped] == [{"a", "b"}, {"c"}]


def test_message_without_id_preserves_first_appearance_order():
    threads = thread_messages(
        [
            Message(payload="first"),
            Message(message_id="a", payload="second"),
        ]
    )

    assert [thread.message.payload for thread in threads] == ["first", "second"]


def test_duplicate_message_id_preserves_first_appearance_order():
    threads = thread_messages(
        [
            Message(message_id="dup", payload="first"),
            Message(message_id="dup", payload="second"),
            Message(message_id="later", payload="third"),
        ]
    )

    assert [thread.message.payload for thread in threads] == [
        "first",
        "second",
        "third",
    ]


def test_raw_references_header_is_parsed_as_message_ids():
    threads = thread_messages(
        [
            Message(message_id="a@example.com"),
            Message(message_id="b@example.com"),
            Message(
                message_id="c@example.com",
                references="<a@example.com> <b@example.com>",
            ),
        ]
    )

    assert len(threads) == 1
    assert _is_ancestor(threads, "a@example.com", "b@example.com")
    assert _is_ancestor(threads, "b@example.com", "c@example.com")


def test_raw_in_reply_to_header_supports_multiple_message_ids():
    threads = thread_messages(
        [
            Message(message_id="a@example.com"),
            Message(message_id="b@example.com"),
            Message(
                message_id="c@example.com",
                in_reply_to="<a@example.com> <b@example.com>",
            ),
        ]
    )

    assert len(threads) == 1
    assert _is_ancestor(threads, "a@example.com", "b@example.com")
    assert _is_ancestor(threads, "b@example.com", "c@example.com")
