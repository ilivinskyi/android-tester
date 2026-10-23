from adtlib import apps

QUERY_ACTIVITIES = """27 activities found:
  com.android.chrome/com.google.android.apps.chrome.Main
  com.google.android.gm/.ConversationListActivityGmail
  com.example.notes/com.example.notes.MainActivity
  com.example.notes/com.example.notes.QuickNote
"""

APPS = [
    ("com.google.android.gm", "Gmail"),
    ("com.android.chrome", "Chrome"),
    ("com.google.android.apps.maps", "Maps"),
    ("com.example.notes", "Quick Notes"),
    ("org.example.notebook", "Notebook Pro"),
]


def test_parse_launcher_packages_dedupes():
    assert apps.parse_launcher_packages(QUERY_ACTIVITIES) == [
        "com.android.chrome", "com.google.android.gm", "com.example.notes"]


def test_label_match_finds_apps_whose_package_differs_from_the_name():
    assert [m.package for m in apps.rank("gmail", APPS)][0] == "com.google.android.gm"


def test_exact_package_and_case_insensitive_label():
    assert apps.rank("com.android.chrome", APPS)[0].score == 100
    assert apps.rank("CHROME", APPS)[0].package == "com.android.chrome"


def test_several_candidates_best_first():
    ranked = apps.rank("note", APPS)
    assert [m.label for m in ranked] == ["Notebook Pro", "Quick Notes"]


def test_typo_still_matches_and_unrelated_is_dropped():
    assert apps.rank("gmial", APPS)[0].label == "Gmail"
    assert apps.rank("weather", APPS) == []
