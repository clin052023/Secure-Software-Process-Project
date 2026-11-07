'''
Courtney Lin, Nicholas Marden
Task-4: install the post-merge git hook.

    python3 install.py

Copies githooks/post-merge into .git/hooks/post-merge and makes it executable,
so every `git pull` / `git merge` checks (and if needed installs) dependencies
and then runs the tests. Run once per clone; nothing else is needed.
'''

import os
import shutil
import stat
import sys

SOURCE = os.path.join("githooks", "post-merge")
HOOK_NAMES = ("post-merge",)


def _git_dir():
    # Works with worktrees and submodules too: .git can be a file, not a folder.
    if os.path.isdir(".git"):
        return ".git"
    if os.path.isfile(".git"):
        with open(".git") as handle:
            line = handle.readline().strip()
        if line.startswith("gitdir:"):
            return line.split(":", 1)[1].strip()
    return None


def main():
    if not os.path.isfile(SOURCE):
        sys.exit(f"Missing {SOURCE}; run this from the project root.")

    git_dir = _git_dir()
    if git_dir is None:
        sys.exit("This is not a git repository. Run `git init` first.")

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    for name in HOOK_NAMES:
        target = os.path.join(hooks_dir, name)
        shutil.copyfile(SOURCE, target)
        mode = os.stat(target).st_mode
        os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Installed: {os.path.normpath(target)}")

    print("\nEvery `git pull` and `git merge` now checks dependencies and runs")
    print("the tests. To remove it:  rm .git/hooks/post-merge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
