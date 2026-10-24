from datetime import date

from mobiletester.core import project, session

DAY = date(2026, 10, 23)


def _project(tmp_path, config: str, profile: str | None = None):
    (tmp_path / ".mobile-tester").mkdir()
    (tmp_path / ".mobile-tester" / "config.yaml").write_text(config, encoding="utf-8")
    if profile is not None:
        app = tmp_path / ".mobile-tester" / "apps" / "com.example.notes"
        app.mkdir(parents=True)
        (app / "profile.yaml").write_text(profile, encoding="utf-8")
    nested = tmp_path / "work" / "deeper"
    nested.mkdir(parents=True)
    return nested


def test_run_folder_goes_to_the_configured_reports_dir_found_from_a_subfolder(tmp_path):
    start = _project(tmp_path, "reports:\n  dir: qa-reports\n", "name: Notes Pro\n")
    run = project.default_run_dir("com.example.notes", "repro", "https://jira.example.com/browse/PROJ-12",
                                  start=start, today=DAY)
    assert run == tmp_path / "qa-reports" / "2026-10-23-notes-pro-repro-proj-12"


def test_new_session_never_reuses_a_folder(tmp_path):
    start = _project(tmp_path, "reports:\n  dir: reports\n")
    first = project.default_run_dir("com.example.notes", "explore", start=start, today=DAY)
    assert first.name == "2026-10-23-notes-explore"  # no profile: last part of the package
    first.mkdir(parents=True)
    assert project.default_run_dir("com.example.notes", "explore", start=start, today=DAY).name == \
        "2026-10-23-notes-explore-2"


def test_without_a_config_reports_go_next_to_where_adt_runs(tmp_path):
    assert project.load(tmp_path) == ({}, tmp_path.resolve())
    assert project.default_run_dir(None, None, start=tmp_path, today=DAY) == \
        tmp_path.resolve() / "reports" / "2026-10-23-session-explore"
    assert project.tester(tmp_path) is None


def test_template_placeholder_name_is_not_used_as_the_app_name(tmp_path):
    start = _project(tmp_path, "tester:\n  name: Ihor\n", "name: <App name>\n")
    assert project.default_title("com.example.notes", "ui-review", start) == "notes Android - UI review"
    assert project.tester(start) == "Ihor"


def test_session_defaults_fill_only_missing_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("MT_HOME", str(tmp_path / ".adt"))
    run = tmp_path / "run"
    session.start("s1", run, {"mode": "explore"}, {"tester": "Ihor", "title": "Notes Android - exploratory test"})
    (run / "session.json").write_text('{"tester": "Someone else", "mode": "explore"}', encoding="utf-8")
    session.start("s1", run, {"mode": "repro"}, {"tester": "Ihor", "title": "T"})
    data = (run / "session.json").read_text(encoding="utf-8")
    assert '"tester": "Someone else"' in data and '"mode": "repro"' in data and '"title": "T"' in data
