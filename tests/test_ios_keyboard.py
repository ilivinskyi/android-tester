"""Typing through the real iOS keyboard layers captured from the simulator (letters, numbers, symbols)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from mobiletester.ios import hierarchy, keyboard

FIXTURES = Path(__file__).parent / "fixtures"


def _keys(name: str):
    _, kb = hierarchy.parse(json.loads((FIXTURES / name).read_text(encoding="utf-8")))
    return kb.keys


class FakeKeyboard:
    """Behaves like the iOS keyboard: shift lasts one letter, layer keys switch layers."""

    def __init__(self, shift: bool = True):
        upper = _keys("ios_habits_edit_keyboard.json")
        self.layers = {
            "upper": upper,
            "lower": [replace(k, label=k.label.lower()) if len(k.label) == 1 else k for k in upper],
            "numbers": _keys("ios_keyboard_numbers.json"),
            "symbols": _keys("ios_keyboard_symbols.json"),
        }
        self.layer = "upper" if shift else "lower"
        self.typed = ""
        self.presses = 0
        self.reads = 0

    def read(self):
        self.reads += 1
        return self.layers[self.layer]

    def press(self, key):
        self.presses += 1
        assert key in self.layers[self.layer], f"pressed {key.label} on the {self.layer} layer"
        moves = {"shift": "lower" if self.layer == "upper" else "upper", "numbers": "numbers",
                 "symbols": "symbols", "letters": "lower"}
        if key.label in moves:
            self.layer = moves[key.label]
            return
        if key.label == "delete":
            self.typed = self.typed[:-1]
            return
        self.typed += keyboard.types(key)
        if self.layer == "upper":
            self.layer = "lower"


@pytest.mark.parametrize("text", ["Run", "run", "Run 5k, daily!", "a&b @home", "x [1] #2 €3", "Hello World"])
def test_types_text_across_layers(text):
    kb = FakeKeyboard()
    keyboard.Typist(kb.read, kb.press).type(text)
    assert kb.typed == text


def test_lowercase_letters_reuse_the_keys_already_read():
    kb = FakeKeyboard(shift=False)
    keyboard.Typist(kb.read, kb.press).type("habit")
    assert kb.typed == "habit" and kb.reads == 1 and kb.presses == 5


def test_auto_capital_at_the_start_is_switched_off_for_lowercase():
    kb = FakeKeyboard(shift=True)
    keyboard.Typist(kb.read, kb.press).type("run")
    assert kb.typed == "run" and kb.presses == 4  # shift off, then r, u, n


def test_a_character_on_no_layer_stops_with_how_much_was_typed():
    kb = FakeKeyboard(shift=False)
    with pytest.raises(keyboard.CannotType) as caught:
        keyboard.Typist(kb.read, kb.press).type("café")
    assert caught.value.typed == 3 and kb.typed == "caf"


def test_no_keyboard():
    with pytest.raises(keyboard.NoKeyboard):
        keyboard.Typist(lambda: [], lambda key: None).type("a")
