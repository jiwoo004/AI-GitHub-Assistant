"""Non-destructive checks for backend.git_utils functions.

Usage: python scripts/check_git_utils.py /path/to/git/repo
"""
import sys
from pathlib import Path

import importlib.util

# Try to import backend.git_utils; if backend isn't a package (no __init__.py),
# load the module directly from the backend directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = PROJECT_ROOT / 'backend' / 'git_utils.py'
if BACKEND_PATH.exists():
    spec = importlib.util.spec_from_file_location('git_utils_local', str(BACKEND_PATH))
    git_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(git_utils)
else:
    # Fallback to normal import if file not found (should raise clearly)
    from backend import git_utils


#!/usr/bin/env python3
"""Non-destructive checks for backend.git_utils functions.

Usage: python scripts/check_git_utils.py /path/to/git/repo
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from backend import git_utils` works
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import git_utils


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_git_utils.py /path/to/git/repo")
        return 1
    repo = sys.argv[1]
    p = Path(repo)
    if not p.exists():
        print("Path does not exist:", repo)
        return 1

    print("is_git_repo:", git_utils.is_git_repo(cwd=repo))
    print("current_branch:", git_utils.current_branch(cwd=repo))
    print("staged_files:", git_utils.staged_files(cwd=repo))
    print("unstaged_files:", git_utils.unstaged_files(cwd=repo))
    print("staged_diff_size bytes:", git_utils.staged_diff_size(cwd=repo))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
