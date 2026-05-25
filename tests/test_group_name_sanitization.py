import os

# Ensure import of helpers.outline succeeds without env-driven side effects.
os.environ.pop("SYNC_GROUP_REGEX", None)

from helpers.outline import _sanitize_group_name  # noqa: E402


def test_strips_crlf_and_tabs():
    assert _sanitize_group_name("foo\r\nbar\tbaz") == "foobarbaz"


def test_strips_other_ascii_control_chars():
    assert _sanitize_group_name("ab\x00cd\x1fef\x7fgh") == "abcdefgh"


def test_preserves_unicode():
    # Group names may legitimately contain unicode; do not strip them.
    name = "engineering über team ñ"
    assert _sanitize_group_name(name) == name


def test_strips_surrounding_whitespace():
    assert _sanitize_group_name("  spaced  ") == "spaced"


def test_no_op_on_plain_name():
    assert _sanitize_group_name("Engineering") == "Engineering"
