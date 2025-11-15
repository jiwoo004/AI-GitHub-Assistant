import subprocess
import os
from typing import List, Optional

# Configurable git executable path. Default to system 'git' on PATH.
GIT_BIN: str = os.environ.get("GIT_EXECUTABLE", "git")


def set_git_executable(path: str) -> None:
    """Set the git executable path used by run_git_command.

    Provide a full path (e.g. /opt/homebrew/bin/git) or a command name on PATH.
    """
    global GIT_BIN
    if path:
        GIT_BIN = path


def get_git_executable() -> str:
    """Return currently configured git executable."""
    return GIT_BIN
from typing import List, Optional, Dict
import io


class GitConflictError(RuntimeError):
    """Raised when a git operation results in a conflict."""
    pass


def run_git_command(args: List[str], cwd: str = None, check: bool = True) -> str:
    cmd = [GIT_BIN] + args
    proc = subprocess.run(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
    )
    if check and proc.returncode != 0:
        if "merge failed" in proc.stderr.lower() and "fix conflicts" in proc.stderr.lower():
            raise GitConflictError(f"Merge conflict detected:\n{proc.stderr}")
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def is_git_repo(cwd: str = None) -> bool:
    try:
        out = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
        return out.strip() == "true"
    except Exception:
        return False


def current_branch(cwd: str = None) -> Optional[str]:
    try:
        out = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        return out.strip()
    except Exception:
        return None


def staged_files(cwd: str = None) -> List[str]:
    if not is_git_repo(cwd=cwd):
        return []
    # Use --cached for wider compatibility (older git may not support --staged)
    out = run_git_command(["diff", "--name-only", "--cached"], cwd=cwd)
    return [line for line in out.splitlines() if line.strip()]


def unstaged_files(cwd: str = None) -> List[str]:
    if not is_git_repo(cwd=cwd):
        return []
    out = run_git_command(["ls-files", "--modified"], cwd=cwd)
    return [line for line in out.splitlines() if line.strip()]

def conflicted_files(cwd: str = None) -> List[str]:
    """List files with merge conflicts."""
    if not is_git_repo(cwd=cwd):
        return []
    # 'U' filter means unmerged. check=False because it can return non-zero code.
    out = run_git_command(["diff", "--name-only", "--diff-filter=U"], cwd=cwd, check=False)
    return [line for line in out.splitlines() if line.strip()]

def get_file_content(file_path: str, cwd: str = None) -> str:
    """Get the content of a file in the working directory."""
    full_path = os.path.join(cwd, file_path)
    with io.open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def stage_file(file_path: str, cwd: str = None) -> str:
    """Stage a single file."""
    return run_git_command(["add", file_path], cwd=cwd)


def diff_staged(cwd: str = None) -> str:
    if not is_git_repo(cwd=cwd):
        return ""
    return run_git_command(["diff", "--cached"], cwd=cwd)


def staged_diff_size(cwd: str = None) -> int:
    """Return approximate size (bytes) of staged diff to guard large requests."""
    if not is_git_repo(cwd=cwd):
        return 0
    d = diff_staged(cwd=cwd)
    return len(d.encode("utf-8"))


def commit(message: str, cwd: str = None) -> str:
    # simple wrapper, raises on failure
    return run_git_command(["commit", "-m", message], cwd=cwd)


def safe_commit(message: str, cwd: str = None, max_diff_bytes: int = 2_000_000) -> str:
    """Commit only if staged diff is under max_diff_bytes. Returns commit stdout."""
    size = staged_diff_size(cwd=cwd)
    if size > max_diff_bytes:
        raise RuntimeError(f"Staged diff too large ({size} bytes), refusing to commit")
    return commit(message, cwd=cwd)


# ===== Branch management =====

def list_branches(cwd: str = None) -> List[str]:
    """List all local branches (removes * marker)."""
    if not is_git_repo(cwd=cwd):
        return []
    out = run_git_command(["branch", "--list"], cwd=cwd)
    branches = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("* "):
            branches.append(line[2:])  # Remove "* " prefix
        elif line:
            branches.append(line)
    return branches

def get_commit_history(cwd: str = None, limit: int = 100) -> List[Dict[str, str]]:
    """Get commit history as a list of dicts."""
    if not is_git_repo(cwd=cwd):
        return []
    
    # Using a custom format with a unique separator to make parsing robust
    # %H: hash, %an: author, %ar: relative date, %s: subject
    log_format = "%H|%an|%ar|%s"
    out = run_git_command(["log", f"--pretty=format:{log_format}", f"-n{limit}"], cwd=cwd)
    
    history = []
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            history.append({
                "hash": parts[0][:7], # Short hash
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            })
    return history

def get_commit_diff(commit_hash: str, cwd: str = None) -> str:
    """Get the diff for a specific commit hash."""
    if not is_git_repo(cwd=cwd):
        return ""
    return run_git_command(["show", "--patch", "--unified=10", commit_hash], cwd=cwd)

def checkout_branch(branch: str, cwd: str = None) -> str:
    """Switch to another branch."""
    return run_git_command(["checkout", branch], cwd=cwd)


def create_branch(branch: str, cwd: str = None) -> str:
    """Create a new branch."""
    return run_git_command(["checkout", "-b", branch], cwd=cwd)


# ===== Push/Pull/Merge operations =====

def push(cwd: str = None) -> str:
    """Push current branch to remote."""
    return run_git_command(["push"], cwd=cwd)


def fetch_remote(cwd: str = None) -> str:
    """Fetch updates from the default remote."""
    return run_git_command(["fetch"], cwd=cwd)


def get_incoming_commits(cwd: str = None) -> List[Dict[str, str]]:
    """
    Get a list of commits that are on the remote but not on the local branch.
    Assumes 'git fetch' has been run recently.
    """
    if not is_git_repo(cwd=cwd):
        return []
    
    try:
        # @{u} or @{upstream} refers to the upstream branch for the current branch.
        # This will fail if no upstream is configured, which is fine.
        log_format = "%H|%an|%ar|%s"
        out = run_git_command(["log", f"--pretty=format:{log_format}", f"HEAD..@{{u}}"], cwd=cwd, check=False)
        return _parse_log_output(out)
    except RuntimeError:
        return [] # Likely no upstream configured


def pull(cwd: str = None) -> str:
    """Pull from remote to current branch."""
    return run_git_command(["pull"], cwd=cwd)


def merge(branch: str, cwd: str = None) -> str:
    """Merge another branch into current branch."""
    return run_git_command(["merge", branch], cwd=cwd)


# ===== Undo operations =====

def undo_last_commit(cwd: str = None) -> str:
    """Undo last commit but keep changes staged (soft reset)."""
    return run_git_command(["reset", "--soft", "HEAD~1"], cwd=cwd)


def undo_last_commit_hard(cwd: str = None) -> str:
    """Undo last commit and discard changes (hard reset)."""
    return run_git_command(["reset", "--hard", "HEAD~1"], cwd=cwd)


def abort_merge(cwd: str = None) -> str:
    """Abort an ongoing merge."""
    return run_git_command(["merge", "--abort"], cwd=cwd)


def abort_rebase(cwd: str = None) -> str:
    """Abort an ongoing rebase."""
    return run_git_command(["rebase", "--abort"], cwd=cwd)


def reset_unstaged(cwd: str = None) -> str:
    """Discard unstaged changes (reset working directory)."""
    return run_git_command(["checkout", "."], cwd=cwd)


def discard_unstaged_file_changes(file_path: str, cwd: str = None) -> str:
    """Discard unstaged changes for a single file."""
    return run_git_command(["checkout", "--", file_path], cwd=cwd)


def reset_staged(cwd: str = None) -> str:
    """Unstage all staged changes."""
    return run_git_command(["reset"], cwd=cwd)


def reset_file(file_path: str, cwd: str = None) -> str:
    """Unstage a single file."""
    return run_git_command(["reset", "HEAD", "--", file_path], cwd=cwd)


def find_git_repos(root: str, max_depth: int = 3, include_hidden: bool = False) -> List[str]:
    """Search for git repositories under `root` up to `max_depth` levels.

    Returns a list of absolute paths that are git repositories.
    This function uses the `find` command for performance and robustness.
    """
    if not root:
        return []
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        return []

    # Using 'find' command. Depth 0 in os.walk is the root itself.
    # `find -maxdepth 1` searches the root. So we need max_depth + 1.
    command = ["find", root, "-maxdepth", str(max_depth + 1), "-type", "d", "-name", ".git"]

    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30  # 30-second timeout for the whole find operation
        )

        git_dirs = proc.stdout.strip().splitlines()
        repo_paths = [os.path.dirname(p) for p in git_dirs]
        
        final_results = []
        for path in repo_paths:
            # Simple filter for hidden paths.
            if not include_hidden and "/." in path.replace(root, ""):
                continue

            try:
                if is_git_repo(cwd=path):
                    final_results.append(path)
            except Exception:
                # is_git_repo might fail (e.g. timeout), skip the path.
                pass
        return final_results

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback or error. Raising an error is better for the UI to handle.
        raise RuntimeError(f"저장소 검색 실패 ('find' 명령어 실행 오류 또는 시간 초과)")
    except Exception as e:
        raise RuntimeError(f"저장소 검색 중 예기치 않은 오류 발생: {e}")


def find_all_git_repos(timeout_seconds: int = 60) -> List[str]:
    """
    Find all git repositories under the user's home directory.

    Uses the `find` command for efficiency. This can be slow.
    A timeout is included to prevent it from running indefinitely.
    """
    home = os.path.expanduser("~")
    command = ["find", home, "-type", "d", "-name", ".git"]
    
    try:
        # Execute the find command with a timeout
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds
        )
        if proc.returncode != 0:
            # Some directories may be unreadable, find might return non-zero.
            # We can still process the output it managed to produce.
            pass

        # Process the output
        paths = proc.stdout.strip().splitlines()
        # The command finds /.git folders, we want the parent directory
        repo_paths = [os.path.dirname(p) for p in paths]
        return repo_paths

    except FileNotFoundError:
        # This could happen if 'find' is not available, though it's unlikely on macOS/Linux.
        raise RuntimeError("The 'find' command is not available on this system.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Repository search timed out after {timeout_seconds} seconds.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while searching for repositories: {e}")
