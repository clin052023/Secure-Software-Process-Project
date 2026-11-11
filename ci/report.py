'''
Courtney Lin, Nicholas Marden
Task-4: turn the JUnit XML written by each task's pytest run into a single
pass/fail report in the GitHub Actions run summary.

    python ci/report.py

Reads reports/task-*.xml, writes a markdown table to $GITHUB_STEP_SUMMARY (when
running in Actions, otherwise to stdout), and exits non-zero if any suite failed
or never ran. This is why every test step uses `continue-on-error: true`: all
three suites report even when the first one is red.
'''

import glob
import os
import sys
import xml.etree.ElementTree as ET

TASKS = [
    ("task-1", "Task-1 Extractor"),
    ("task-2", "Task-2 Comparator"),
    ("task-3", "Task-3 Executor"),
]


def _read(path):
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise ValueError("no <testsuite> element")
    tests = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    seconds = float(suite.get("time", 0.0))
    return tests, tests - failures - errors - skipped, failures, errors, skipped, seconds


def main():
    rows, failed = [], False
    for key, label in TASKS:
        path = os.path.join("reports", f"{key}.xml")
        if not os.path.isfile(path):
            rows.append((label, "**did not run**", "-", "-", "-", "-"))
            failed = True
            continue
        tests, passed, failures, errors, skipped, seconds = _read(path)
        green = failures == 0 and errors == 0 and tests > 0
        failed = failed or not green
        rows.append((
            label,
            "**pass**" if green else "**fail**",
            tests,
            passed,
            failures + errors,
            f"{seconds:.2f}s",
        ))

    out = ["", "## Test results", "",
           "| Suite | Result | Tests | Passed | Failed | Time |",
           "|---|---|---|---|---|---|"]
    out += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |" for r in rows]
    text = "\n".join(out) + "\n"

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)

    if failed:
        print("One or more task suites failed (or did not run).", file=sys.stderr)
        return 1
    print("All task suites passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
