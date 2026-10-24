import pytest

from mobiletester.core.guard import classify


@pytest.mark.parametrize(
    ("label", "rid", "expected"),
    [
        ("Buy now", "", "payment"),
        ("", "btn_buyNow", "payment"),
        ("Start free trial", "", "payment"),
        ("Subscribe", "", "payment"),
        ("Send", "", "message"),
        ("Post comment", "", "message"),
        ("Log out", "", "account"),
        ("Sign out", "", "account"),
        ("Delete account", "", "account"),
        ("Settings", "", None),
        ("Sign in", "login_btn", None),
        ("Payments history", "", None),
        ("Buyer protection info", "", None),
    ],
)
def test_classify(label, rid, expected):
    assert classify(label, rid) == expected
