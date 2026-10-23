import pytest

from adtlib.device import escape_input_text


def test_escape_spaces_and_shell_chars():
    assert escape_input_text("a b") == "a%sb"
    assert escape_input_text("p@ss$word!") == "p@ss\\$word\\!"
    assert escape_input_text("it's (ok)") == "it\\'s%s\\(ok\\)"


def test_escape_rejects_non_ascii_and_newlines():
    with pytest.raises(ValueError):
        escape_input_text("Привіт")
    with pytest.raises(ValueError):
        escape_input_text("line1\nline2")
