from adtlib import state


def test_state_found_from_a_subfolder_of_the_project(tmp_path, monkeypatch):
    monkeypatch.delenv("ADT_HOME", raising=False)
    (tmp_path / ".adt").mkdir()
    run = tmp_path / "reports" / "2026-10-23-app-explore" / "logs"
    run.mkdir(parents=True)
    monkeypatch.chdir(run)
    assert state.home() == (tmp_path / ".adt").resolve()


def test_project_marked_by_android_tester_config(tmp_path, monkeypatch):
    monkeypatch.delenv("ADT_HOME", raising=False)
    (tmp_path / ".android-tester").mkdir()
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    assert state.home() == (tmp_path / ".adt").resolve()


def test_new_project_uses_current_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("ADT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert state.home() == (tmp_path / ".adt").resolve()


def test_adt_home_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("ADT_HOME", str(tmp_path / "elsewhere"))
    assert state.home() == (tmp_path / "elsewhere").resolve()
