from mobiletester.core import state


def test_state_found_from_a_subfolder_of_the_project(tmp_path, monkeypatch):
    monkeypatch.delenv("MT_HOME", raising=False)
    (tmp_path / ".mobile-tester").mkdir()
    run = tmp_path / "reports" / "2026-10-23-app-explore" / "logs"
    run.mkdir(parents=True)
    monkeypatch.chdir(run)
    assert state.home() == (tmp_path / ".mobile-tester" / "state").resolve()


def test_new_project_uses_current_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("MT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert state.home() == (tmp_path / ".mobile-tester" / "state").resolve()


def test_mt_home_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("MT_HOME", str(tmp_path / "elsewhere"))
    assert state.home() == (tmp_path / "elsewhere").resolve()
