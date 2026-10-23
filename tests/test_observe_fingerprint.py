from adtlib import device, hierarchy


def test_observe_works_without_a_fingerprint(fixture_xml, monkeypatch):
    def unimplemented(*_):
        raise NotImplementedError

    monkeypatch.setattr(device, "screen_fingerprint", unimplemented)
    els = hierarchy.parse(fixture_xml("login_form.xml")).elements
    assert device._fingerprint("com.example.shop", "", els) == "-"


def test_observe_uses_the_fingerprint_once_implemented(fixture_xml, monkeypatch):
    monkeypatch.setattr(device, "screen_fingerprint", lambda *_: "abc123")
    assert device._fingerprint("p", "a", []) == "abc123"
