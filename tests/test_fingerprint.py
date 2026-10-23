"""Contract for screen_fingerprint: same room with different visitors -> same id; different room -> new id."""

import dataclasses

from adtlib import hierarchy
from adtlib.fingerprint import screen_fingerprint

JUMBO, JUMBO_ACT = "com.icemobile.jumboclient", "com.jumbo.fep.MainActivity"
DISPLAY = (1080, 2400)


def _jumbo(fixture_xml, name):
    return screen_fingerprint(JUMBO, JUMBO_ACT, hierarchy.parse(fixture_xml(name), display=DISPLAY).elements)

PKG, ACT = "com.example.shop", "com.example.shop.LoginActivity"


def _elements(fixture_xml):
    return hierarchy.parse(fixture_xml("login_form.xml")).elements


def test_deterministic_short_string(fixture_xml):
    els = _elements(fixture_xml)
    fp = screen_fingerprint(PKG, ACT, els)
    assert isinstance(fp, str) and 6 <= len(fp) <= 40
    assert fp == screen_fingerprint(PKG, ACT, _elements(fixture_xml))


def test_typed_text_does_not_change_identity(fixture_xml):
    els = _elements(fixture_xml)
    typed = [dataclasses.replace(e, text="someone@example.com", label="someone@example.com")
             if e.short_id == "email" else e for e in els]
    assert screen_fingerprint(PKG, ACT, typed) == screen_fingerprint(PKG, ACT, els)


def test_focus_and_check_state_do_not_change_identity(fixture_xml):
    els = _elements(fixture_xml)
    toggled = [dataclasses.replace(e, focused=not e.focused, checked=not e.checked) for e in els]
    assert screen_fingerprint(PKG, ACT, toggled) == screen_fingerprint(PKG, ACT, els)


def test_different_activity_differs(fixture_xml):
    els = _elements(fixture_xml)
    assert screen_fingerprint(PKG, ACT, els) != screen_fingerprint(PKG, PKG + ".SignupActivity", els)


def test_same_activity_different_structure_differs(fixture_xml):
    els = _elements(fixture_xml)
    without_password = [e for e in els if e.short_id not in ("password", "remember")]
    assert screen_fingerprint(PKG, ACT, without_password) != screen_fingerprint(PKG, ACT, els)


def test_jumbo_search_results_stay_one_screen(fixture_xml):
    # Same search screen: before adding milk, with the quantity stepper, and with "Mandje 1 product".
    ids = {_jumbo(fixture_xml, f) for f in ("jumbo_search_results.xml", "jumbo_stepper_no_keyboard.xml",
                                             "jumbo_search_with_basket.xml")}
    assert len(ids) == 1


def test_keyboard_wrapper_scroll_doesnt_swallow_the_header(fixture_xml):
    # With the keyboard open the web page wraps everything in one more scroll container. The header must
    # still count; the screen only differs by the tab bar the app hides while typing.
    assert _jumbo(fixture_xml, "jumbo_stepper.xml") != _jumbo(fixture_xml, "jumbo_search_results.xml")
    els = hierarchy.parse(fixture_xml("jumbo_stepper.xml"), display=DISPLAY).elements
    no_tabs = [e for e in hierarchy.parse(fixture_xml("jumbo_search_results.xml"), display=DISPLAY).elements
               if not (e.clickable and e.label.startswith(("Start", "Producten", "Recepten", "Aanbiedingen",
                                                             "Mandje")) and e.bounds.top > 2100)]
    assert screen_fingerprint(JUMBO, JUMBO_ACT, els) == screen_fingerprint(JUMBO, JUMBO_ACT, no_tabs)


def test_jumbo_screens_in_one_activity_differ(fixture_xml):
    # Jumbo is one Activity with web content: only the screens' fixed parts tell them apart.
    screens = ["jumbo_home.xml", "jumbo_categories.xml", "jumbo_recipes.xml", "jumbo_search_results.xml",
               "jumbo_basket.xml"]
    ids = [_jumbo(fixture_xml, f) for f in screens]
    assert len(set(ids)) == len(screens), dict(zip(screens, ids, strict=True))


def test_real_screens_differ(fixture_xml):
    launcher = hierarchy.parse(fixture_xml("launcher_home.xml"))
    settings = hierarchy.parse(fixture_xml("settings_developer.xml"))
    assert screen_fingerprint(launcher.package, "", launcher.elements) != screen_fingerprint(
        settings.package, "", settings.elements
    )
