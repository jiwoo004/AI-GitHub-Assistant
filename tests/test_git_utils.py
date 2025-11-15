import subprocess
import pytest

from backend import git_utils


class DummyProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_is_git_repo_true(monkeypatch):
    def fake_run(cmd, cwd=None, stdout=None, stderr=None, text=None):
        return DummyProc(returncode=0, stdout="true\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert git_utils.is_git_repo(cwd="/some/path") is True


def test_is_git_repo_false(monkeypatch):
    def fake_run(cmd, cwd=None, stdout=None, stderr=None, text=None):
        return DummyProc(returncode=1, stdout="", stderr="fatal: not a git repository")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert git_utils.is_git_repo(cwd="/some/path") is False


def test_current_branch(monkeypatch):
    def fake_run(cmd, cwd=None, stdout=None, stderr=None, text=None):
        return DummyProc(stdout="main\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert git_utils.current_branch(cwd="/p") == "main"


def test_staged_and_unstaged_lists(monkeypatch):
    def fake_run(cmd, cwd=None, stdout=None, stderr=None, text=None):
        # simulate being inside a git work tree
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"] or "--is-inside-work-tree" in cmd:
            return DummyProc(stdout="true\n")
        if "--name-only" in cmd:
            return DummyProc(stdout="file1.py\nfile2.txt\n")
        if cmd[:2] == ["git", "ls-files"]:
            return DummyProc(stdout="file3.md\n")
        return DummyProc(stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    staged = git_utils.staged_files(cwd="/p")
    unstaged = git_utils.unstaged_files(cwd="/p")
    assert staged == ["file1.py", "file2.txt"]
    assert unstaged == ["file3.md"]


def test_diff_and_size_and_safe_commit(monkeypatch):
    # diff returns small content first
    def fake_run_small(cmd, cwd=None, stdout=None, stderr=None, text=None):
        # simulate being inside a git work tree
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"] or "--is-inside-work-tree" in cmd:
            return DummyProc(stdout="true\n")
        if cmd[:2] == ["git", "diff"]:
            return DummyProc(stdout="+ line1\n+ line2\n")
        if cmd[:2] == ["git", "commit"]:
            return DummyProc(stdout="[main abc123] test commit\n")
        return DummyProc(stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run_small)
    d = git_utils.diff_staged(cwd="/p")
    assert "+ line1" in d
    size = git_utils.staged_diff_size(cwd="/p")
    assert size > 0
    # safe commit should succeed for small diff
    out = git_utils.safe_commit("msg", cwd="/p", max_diff_bytes=1000)
    assert "test commit" in out

    # now simulate large diff
    def fake_run_large(cmd, cwd=None, stdout=None, stderr=None, text=None):
        # simulate being inside a git work tree
        if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"] or "--is-inside-work-tree" in cmd:
            return DummyProc(stdout="true\n")
        if cmd[:2] == ["git", "diff"]:
            return DummyProc(stdout="a" * 5_000_000)
        return DummyProc(stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run_large)
    with pytest.raises(RuntimeError):
        git_utils.safe_commit("msg", cwd="/p", max_diff_bytes=1000)
