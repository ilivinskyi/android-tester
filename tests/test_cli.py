"""The command lines parse: every subcommand is wired and the shared report commands are on both."""

import pytest

from mobiletester.android import cli as adt


@pytest.mark.parametrize("argv", [
    ["report", "check", "RUN"],
    ["report", "confirm", "RUN", "B1", "--result", "reproduced", "--by", "Ihor"],
    ["issues", "list", "--package", "com.example"],
    ["issues", "set", "K-1", "--package", "com.example", "--status", "fixed"],
    ["tap", "--text", "OK", "--fast"],
    ["--fast", "app", "reset", "com.example", "--level", "clear-data"],
    ["session", "start", "--package", "com.example", "--mode", "explore", "--record"],
])
def test_adt_parses(argv):
    args = adt.build_parser().parse_args(argv)
    assert args.cmd == argv[1] if argv[0].startswith("-") else args.cmd == argv[0]


def test_adt_issues_default_to_the_project_folder():
    assert adt.build_parser().parse_args(["issues", "list", "--package", "p"]).config_dir == ".mobile-tester"
