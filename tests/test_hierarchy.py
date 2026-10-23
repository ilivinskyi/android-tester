from adtlib import hierarchy
from adtlib.hierarchy import Bounds


def test_bounds_parse_and_geometry():
    b = Bounds.parse("[64,500][1016,640]")
    assert (b.left, b.top, b.right, b.bottom) == (64, 500, 1016, 640)
    assert b.center == (540, 570)
    assert b.contains(64, 500) and not b.contains(1016, 640)


def test_login_form_elements(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    assert snap.package == "com.example.shop"
    assert (snap.screen.right, snap.screen.bottom) == (1080, 2400)
    by_id = {e.short_id: e for e in snap.elements if e.short_id}

    assert by_id["title"].label == "Welcome back" and not by_id["title"].interactive
    assert by_id["email"].editable and by_id["email"].focused and by_id["email"].hint == "Email"
    assert by_id["password"].password
    assert by_id["remember"].checkable and by_id["remember"].checked and by_id["remember"].label == "Remember me"


def test_clickable_container_takes_child_label_and_hides_child(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    row = hierarchy.find_by_id(snap, "login_row")[0]
    assert row.label == "Sign in"
    assert not row.enabled
    assert [e for e in snap.elements if e.label == "Sign in"] == [row]


def test_offscreen_elements_are_dropped(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    assert not hierarchy.find_by_text(snap, "Offscreen")


def test_risky_element_flagged(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    upsell = hierarchy.find_by_text(snap, "buy premium")[0]
    assert upsell.risk == "payment"
    assert "RISK:payment" in upsell.describe()


def test_element_at_prefers_smallest(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    assert hierarchy.element_at(snap, 100, 900).short_id == "remember"
    assert hierarchy.element_at(snap, 5, 5) is None


def test_find_by_text_exact_before_substring(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    assert [e.short_id for e in hierarchy.find_by_text(snap, "Password")] == ["password"]


def test_real_settings_dump(fixture_xml):
    snap = hierarchy.parse(fixture_xml("settings_developer.xml"))
    assert snap.package == "com.android.settings"
    assert any(e.scrollable for e in snap.elements)
    switches = [e for e in snap.elements if e.checkable]
    assert switches, "developer options list has toggles"
    # Rows inside the scrollable list keep their own labels instead of being merged into the list.
    assert hierarchy.find_by_text(snap, "Wait for debugger")


def test_find_by_text_matches_part_of_merged_row_label(fixture_xml):
    snap = hierarchy.parse(fixture_xml("settings_developer.xml"))
    rows = hierarchy.find_by_text(snap, "Wait for debugger")
    assert len(rows) == 1 and rows[0].clickable


def test_real_launcher_dump(fixture_xml):
    snap = hierarchy.parse(fixture_xml("launcher_home.xml"))
    assert snap.package == "com.google.android.apps.nexuslauncher"
    assert all(e.bounds.area > 0 for e in snap.elements)
    assert sum(e.clickable for e in snap.elements) >= 4


def test_element_roundtrip(fixture_xml):
    snap = hierarchy.parse(fixture_xml("login_form.xml"))
    for el in snap.elements:
        assert hierarchy.Element.from_dict(el.to_dict()) == el
