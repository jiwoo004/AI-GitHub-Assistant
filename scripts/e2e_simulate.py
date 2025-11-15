#!/usr/bin/env python3
"""End-to-end simulation test for AI Git Assistant.

This script simulates the full workflow:
1. Create a mock git repository
2. Stage some changes
3. Call AI (mock mode) to generate commit message
4. Simulate commit with safe_commit
5. Verify results

Run with: python scripts/e2e_simulate.py
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import git_utils, ollama_client, config


def setup_test_repo(repo_path: str) -> None:
    """Initialize a git repository and make a staged change."""
    Path(repo_path).mkdir(parents=True, exist_ok=True)
    
    # Initialize git repo
    git_utils.run_git_command(["init"], cwd=repo_path)
    git_utils.run_git_command(["config", "user.email", "test@test.com"], cwd=repo_path)
    git_utils.run_git_command(["config", "user.name", "Test User"], cwd=repo_path)
    
    # Create initial commit
    test_file = Path(repo_path) / "README.md"
    test_file.write_text("# Test Project\n")
    git_utils.run_git_command(["add", "README.md"], cwd=repo_path)
    git_utils.run_git_command(["commit", "-m", "initial commit"], cwd=repo_path)
    
    # Make a staged change
    test_file.write_text("# Test Project\n\nUpdated.\n")
    git_utils.run_git_command(["add", "README.md"], cwd=repo_path)


def main():
    print("=" * 60)
    print("E2E Simulation: AI Git Assistant Workflow")
    print("=" * 60)
    
    # Create temporary test repository
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        
        try:
            print("\n[Step 1] Setting up test git repository...")
            setup_test_repo(str(repo_path))
            print(f"✓ Repository created at {repo_path}")
            
            print("\n[Step 2] Checking repository state...")
            is_git = git_utils.is_git_repo(cwd=str(repo_path))
            branch = git_utils.current_branch(cwd=str(repo_path))
            staged = git_utils.staged_files(cwd=str(repo_path))
            unstaged = git_utils.unstaged_files(cwd=str(repo_path))
            diff_size = git_utils.staged_diff_size(cwd=str(repo_path))
            
            print(f"✓ Is git repo: {is_git}")
            print(f"✓ Current branch: {branch}")
            print(f"✓ Staged files: {staged}")
            print(f"✓ Unstaged files: {unstaged}")
            print(f"✓ Staged diff size: {diff_size} bytes")
            
            if not staged:
                print("⚠ WARNING: No staged files, skipping AI generation")
                return 1
            
            print("\n[Step 3] Generating commit message (mock mode)...")
            # Enable mock mode for this test
            import os
            os.environ["AI_MOCK_MODE"] = "1"
            
            diff = git_utils.diff_staged(cwd=str(repo_path))
            commit_msg = ollama_client.generate_commit_message(diff)
            print(f"✓ Generated commit message: '{commit_msg}'")
            
            print("\n[Step 4] Performing safe commit...")
            try:
                result = git_utils.safe_commit(
                    commit_msg,
                    cwd=str(repo_path),
                    max_diff_bytes=config.load_config().get("max_diff_bytes", 2_000_000)
                )
                print(f"✓ Commit successful: {result.strip()}")
            except RuntimeError as e:
                print(f"✗ Commit failed: {e}")
                return 1
            
            print("\n[Step 5] Verifying final state...")
            staged_after = git_utils.staged_files(cwd=str(repo_path))
            print(f"✓ Staged files after commit: {staged_after}")
            
            if staged_after:
                print("⚠ WARNING: Staged files remain after commit")
            else:
                print("✓ All staged files committed")
            
            print("\n" + "=" * 60)
            print("✓ E2E SIMULATION PASSED")
            print("=" * 60)
            return 0
            
        except Exception as e:
            print(f"\n✗ Error during simulation: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
