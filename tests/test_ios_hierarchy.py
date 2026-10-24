"""The runner's XCUITest snapshots of Loop Habit Tracker (iPhone 17 simulator, iOS 27) as the shared model."""

import json
from pathlib import Path

from mobiletester.core import ui
from mobiletester.ios import hierarchy

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return hierarchy.parse(json.loads((FIXTURES / name).read_text(encoding="utf-8")), "com.github.aint.Habits")


def test_list_screen_lists_title_add_button_and_list():
    snap, keyboard = _load("ios_habits_list.json")
    assert keyboard is None
    assert snap.screen == ui.Bounds(0, 0, 402, 874)
    described = [e.describe() for e in snap.elements]
    add = ui.find_by_text(snap, "Add")
    assert len(add) == 1 and add[0].cls == "Button" and add[0].short_id == "plus" and add[0].clickable
    assert any(e.cls == "CollectionView" and e.scrollable for e in snap.elements)
    assert any(e.cls == "StaticText" and e.label == "Habits" for e in snap.elements)
    # Scroll indicators and full-screen containers are not content.
    assert not any("scroll bar" in d for d in described)
    assert not any(e.label == "Toolbar" for e in snap.elements)


def test_cell_without_label_takes_its_texts():
    snap, _ = _load("ios_habits_list.json")
    cell = next(e for e in snap.elements if e.cls == "Cell")
    assert cell.label.startswith("Name | Sat 24")


def test_text_field_is_editable_with_its_placeholder_as_hint():
    snap, _ = _load("ios_habits_edit.json")
    field = next(e for e in snap.elements if e.editable)
    assert field.cls == "TextField" and field.hint == "Name" and field.text == ""
    assert field.describe().startswith('[5] TextField "Name"')
    assert ui.find_by_text(snap, "Name") == [field]


def test_keyboard_is_an_area_with_keys_not_elements():
    snap, keyboard = _load("ios_habits_edit_keyboard.json")
    assert keyboard is not None
    # The suggestion bar sits above the keys and belongs to the keyboard too.
    assert keyboard.area.top == 546 and keyboard.area.bottom == 874
    labels = {k.label for k in keyboard.keys}
    assert {"Q", "A", "shift", "delete", "numbers", "space", "return"} <= labels
    assert not any(e.cls == "Key" for e in snap.elements)
    field = next(e for e in snap.elements if e.editable)
    assert field.text == ""


def test_rows_behind_the_keyboard_are_not_tappable():
    snap, keyboard = _load("ios_habits_edit_keyboard.json")
    color = ui.find_by_text(snap, "Color")[0]
    assert ui.visible_point(snap, color, (keyboard.area,)) is not None
    hidden = ui.Element(index=99, cls="Button", text="", desc="", resource_id="", hint="",
                        bounds=ui.Bounds(20, 600, 380, 640), label="Hidden", clickable=True, z=[0, 9])
    assert ui.visible_point(snap, hidden, (keyboard.area,)) is None


def test_numbers_and_symbols_layers_are_read():
    _, numbers = _load("ios_keyboard_numbers.json")
    assert {"1", "0", "-", "ampersand", "symbols", "letters"} <= {k.label for k in numbers.keys}
    _, symbols = _load("ios_keyboard_symbols.json")
    assert {"[", "#", "€", "numbers", "letters"} <= {k.label for k in symbols.keys}


def test_risky_buttons_are_flagged():
    data = {"tree": {"type": "Application", "frame": [0, 0, 402, 874], "children": [
        {"type": "Window", "frame": [0, 0, 402, 874], "children": [
            {"type": "Button", "label": "Buy now", "frame": [20, 700, 360, 50]},
            {"type": "Button", "label": "Save", "frame": [20, 600, 360, 50]},
        ]}]}}
    snap, _ = hierarchy.parse(data)
    assert [e.risk for e in snap.elements] == ["payment", None]


def test_system_alert_is_on_top_of_the_app():
    data = {"tree": {"type": "Application", "frame": [0, 0, 402, 874], "children": [
        {"type": "Window", "frame": [0, 0, 402, 874], "children": [
            {"type": "Button", "label": "Behind", "frame": [0, 400, 402, 80]}]}]},
        "alerts": [{"type": "Alert", "label": "Allow notifications?", "frame": [50, 300, 300, 250], "children": [
            {"type": "Button", "label": "Allow", "frame": [50, 430, 300, 50]}]}]}
    snap, _ = hierarchy.parse(data)
    assert ui.element_at(snap, 200, 450).label == "Allow"
