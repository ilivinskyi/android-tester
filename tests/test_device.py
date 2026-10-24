import pytest

from mobiletester.android.device import escape_input_text
from mobiletester.android.human import back_swipe_heights


def test_escape_spaces_and_shell_chars():
    assert escape_input_text("a b") == "a%sb"
    assert escape_input_text("p@ss$word!") == "p@ss\\$word\\!"
    assert escape_input_text("it's (ok)") == "it\\'s%s\\(ok\\)"


def test_escape_rejects_non_ascii_and_newlines():
    with pytest.raises(ValueError):
        escape_input_text("Привіт")
    with pytest.raises(ValueError):
        escape_input_text("line1\nline2")


def test_back_swipe_starts_mid_screen_without_keyboard():
    assert back_swipe_heights(2856, None) == (2856 * 0.35, 2856 * 0.65)


def test_back_swipe_starts_above_an_open_keyboard():
    # Pixel emulator, Gboard open from y=1843: a swipe starting at 1857 went to the keyboard, not back.
    low, high = back_swipe_heights(2856, 1843)
    assert high < 1843 and low < high and low >= 2856 * 0.1
