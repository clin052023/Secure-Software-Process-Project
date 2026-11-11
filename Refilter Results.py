'''
Courtney Lin, Nicholas Marden
Task-3: re-apply the rule restriction to results that were already written.

    python3 "Refilter Results.py"              # every results/Input-*/ folder
    python3 "Refilter Results.py" results/Input-3
    python3 "Refilter Results.py" --dry-run

Task-3 requires Hadolint to run "only on the rules that are in the TEXT file".
run_hadolint() now drops findings for rules outside that file, but a scan that
was made before that change still carries them - typically every ShellCheck rule
(SC2086, SC2028, ...), which cannot be suppressed with --ignore because their
codes are not in the rule table.

The CSV has one row per (FilePath, RULEID) with a COUNT, so removing rows for
out-of-scope rules is arithmetically identical to re-running the whole scan with
the restriction applied: no Hadolint run, seconds instead of ~40 minutes per
input.

When hadolint_rules.txt says NO MAPPING FOUND / NO DIFFERENCES FOUND, every rule
is in scope and the file is left untouched.
'''

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task3_executor.executor import refilter_results_csv   # noqa: E402  (single implementation)

RULES_NAME = "hadolint_rules.txt"
CSV_NAME = "hadolint_results.csv"


def refilter(folder, dry_run=False):
    csv_path = os.path.join(folder, CSV_NAME)
    rules_path = os.path.join(folder, RULES_NAME)
    if not (os.path.isfile(csv_path) and os.path.isfile(rules_path)):
        print(f"  {folder}: skipped (needs {CSV_NAME} and {RULES_NAME})")
        return None
    kept, dropped = refilter_results_csv(csv_path, rules_path, dry_run=dry_run)
    verb = "would drop" if dry_run else "dropped"
    print(f"  {folder}: kept {kept} row(s), {verb} {dropped} out-of-scope row(s)")
    return (kept, dropped)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("folders", nargs="*", default=None,
                        help="result folders (default: results/Input-*/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be dropped, change nothing")
    args = parser.parse_args()

    folders = args.folders
    if not folders:
        base = "results"
        if not os.path.isdir(base):
            sys.exit(f"Nothing to do: no '{base}/' folder. Pass a folder explicitly.")
        folders = sorted(os.path.join(base, name) for name in os.listdir(base)
                         if os.path.isdir(os.path.join(base, name)))

    total_dropped = 0
    for folder in folders:
        result = refilter(folder, dry_run=args.dry_run)
        if result is not None:
            total_dropped += result[1]

    print(f"\n{total_dropped} out-of-scope row(s) "
          f"{'would be ' if args.dry_run else ''}removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
