''' 
Courtney Lin, Nicholas Marden
Task 3 - Executor
'''

# ------------------------------------------- #
#          - Executor Test Cases -            #
# ------------------------------------------- #

# One test case for each of the four functions in executor.py.
# Run in terminal (from the project root):
#     python3 -m unittest task3_executor.test_executor -v
#     python3 -m unittest discover -v
#
# run_hadolint() needs the Hadolint binary. It is looked for in this order:
#   1) the HADOLINT environment variable
#   2) `hadolint` on PATH
# If neither exists that one test is skipped, the other three still run.

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import pandas as pd

# executor.py is imported as part of the task3_executor package when pytest runs
# from the project root, and as a loose module when the file is run from inside
# this folder. A couple of tests import it lazily by name, so register both.
try:
    from . import executor as _executor_module
    sys.modules.setdefault("executor", _executor_module)
except ImportError:                     # plain script run from inside the folder
    pass

try:                                    # `python3 -m unittest ...` (package import)
    from .executor import (read_difference_files, map_differences_to_rules,
                           run_hadolint, write_summary_csv, write_failure_csv,
                           refilter_results_csv, RULES,
                           HADOLINT_WORKERS, HADOLINT_WORKERS_ENV, _resolve_workers,
                           NO_DIFFERENCES, NO_MAPPING)
except ImportError:                     # plain script run from inside the folder
    from executor import (read_difference_files, map_differences_to_rules,
                          run_hadolint, write_summary_csv, write_failure_csv,
                          refilter_results_csv, RULES,
                          HADOLINT_WORKERS, HADOLINT_WORKERS_ENV, _resolve_workers,
                          NO_DIFFERENCES, NO_MAPPING)


NAMES_TXT = """Names only in file 1:
Docker Auditing
Docker Shim Runc V1 Auditing

Names only in file 2:
Containerization
Docker Daemon Access
"""

REQS_TXT = """Requirements only in file 1:
Docker Auditing,Add a rule for the docker daemon configuration file
Docker Auditing,Ensure the container runs as a non-root user

Requirements only in file 2:
Containerization,Pin versions in apt-get install
"""


def hadolint_command():
    # Resolves the Hadolint binary, or returns None when it is not installed.
    return os.environ.get("HADOLINT") or shutil.which("hadolint")


class TestExecutorFunctions(unittest.TestCase):

    # Run in a temporary directory so the hardcoded output filenames do not
    # overwrite real output files.

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        with open("difference_names.txt", "w") as f:
            f.write(NAMES_TXT)
        with open("difference_requirements.txt", "w") as f:
            f.write(REQS_TXT)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()


    # ------------------------------------------ #
    #          - Function Test Cases -           #
    # ------------------------------------------ #

    def test_read_difference_files(self):

        data = read_difference_files()

        # Both sections of both files, in order, with the "NAME,REQU" lines split.
        self.assertEqual(data["names"]["file1"],
                         ["Docker Auditing", "Docker Shim Runc V1 Auditing"])
        self.assertEqual(data["names"]["file2"],
                         ["Containerization", "Docker Daemon Access"])
        self.assertEqual(data["requirements"]["file1"][1],
                         ("Docker Auditing", "Ensure the container runs as a non-root user"))
        self.assertEqual(data["requirements"]["file2"],
                         [("Containerization", "Pin versions in apt-get install")])
        self.assertTrue(data["has_differences"])

        # A file that only reports no differences must not count as a difference.
        with open("difference_names.txt", "w") as f:
            f.write("NO DIFFERENCES FOUND\n")
        with open("difference_requirements.txt", "w") as f:
            f.write("NO DIFFERENCES FOUND\n")
        self.assertFalse(read_difference_files()["has_differences"])

        # Same validation style as the rest of the project: bad path, wrong
        # extension, and a requirements file fed in as a names file.
        with self.assertRaises(FileNotFoundError):
            read_difference_files(names_path="missing.txt")
        with open("names.csv", "w") as f:
            f.write("whatever\n")
        with self.assertRaises(ValueError):
            read_difference_files(names_path="names.csv")
        with self.assertRaises(TypeError):
            read_difference_files(names_path="   ")


    def test_map_differences_to_rules(self):

        result = map_differences_to_rules()
        with open("hadolint_rules.txt") as f:
            lines = [ln.strip() for ln in f if ln.strip()]

        self.assertEqual(result["status"], "differences")
        self.assertTrue(lines)

        # Every line is "DLRULE,severity,message" and the rule is one Hadolint knows.
        for line in lines:
            code, severity, message = line.split(",", 2)
            self.assertIn(code, RULES)
            self.assertEqual(severity, RULES[code][0])
            self.assertTrue(message)

        # "non-root user" is CIS 4.1, which maps to more than one rule: one KDE
        # mapping to several requirements is exactly the intended behaviour.
        non_root = [m for m in result["matches"] if "non-root" in m["requirement"].lower()]
        self.assertTrue(non_root)
        self.assertIn("DL3002", non_root[0]["rules"])
        self.assertIn("DL3002", result["rules"])
        # And apt-get pinning (CIS 4.11) picks up DL3008.
        self.assertIn("DL3008", result["rules"])

        # No differences at all -> NO DIFFERENCES FOUND, no rules.
        with open("difference_names.txt", "w") as f:
            f.write("NO DIFFERENCES FOUND\n")
        with open("difference_requirements.txt", "w") as f:
            f.write("NO DIFFERENCES FOUND\n")
        result = map_differences_to_rules()
        with open("hadolint_rules.txt") as f:
            self.assertEqual(f.read().strip(), NO_DIFFERENCES)
        self.assertEqual(result["status"], "no_differences")
        self.assertEqual(result["rules"], [])

        # Differences that map to nothing -> NO MAPPING FOUND, no rules.
        # These are real host-level CIS items: no Dockerfile instruction can
        # express them, so the README's second outcome applies.
        with open("difference_names.txt", "w") as f:
            f.write("Names only in file 1:\n"
                    "Docker Auditing\n"
                    "Containerization\n")
        with open("difference_requirements.txt", "w") as f:
            f.write("Requirements only in file 1:\n"
                    "Docker Auditing,Add a rule for the /etc/docker/daemon.json file.\n"
                    "Containerization,Ensure a separate partition for containers has been created\n")
        result = map_differences_to_rules()
        with open("hadolint_rules.txt") as f:
            contents = f.read().strip()
        # The file must hold exactly one of the three allowed contents.
        self.assertEqual(contents, NO_MAPPING)
        self.assertEqual(result["status"], "no_mapping")
        self.assertEqual(result["rules"], [])
        # The unmappable CIS items are reported back so the run can be explained.
        unmappable_titles = " ".join(u[1] for u in result["unmappable"])
        self.assertIn("separate partition", unmappable_titles)
        self.assertIn("auditing", unmappable_titles.lower())


    def test_map_matches_phrasing_not_exact_phrases(self):

        # The 1B model paraphrases, so the same CIS item arrives in many shapes.
        # Each of these is a real-looking rewrite of a Dockerfile-relevant item
        # and must still map; an exact-phrase matcher missed most of them.
        cases = [
            ("Instruction Choice", "COPY must be used instead of ADD",
             "DL3020"),                                            # CIS 4.9
            ("Instruction Choice", "Use COPY rather than ADD",
             "DL3020"),                                            # CIS 4.9
            ("Image Base", "The base image tag must be a pinned version",
             "DL3007"),                                            # CIS 4.2
            ("Package Cache", "The package cache should be cleaned up after installing",
             "DL3009"),                                            # CIS 4.3
            ("Health Probe", "A HEALTHCHECK instruction must be added to the image",
             "DL3012"),                                            # CIS 4.6
            ("User", "The container must not run as the root user",
             "DL3002"),                                            # CIS 4.1
        ]

        for name, requirement, expected in cases:
            with open("difference_names.txt", "w") as f:
                f.write(f"Names only in file 1:\n{name}\n")
            with open("difference_requirements.txt", "w") as f:
                f.write(f"Requirements only in file 1:\n{name},{requirement}\n")

            result = map_differences_to_rules()
            self.assertEqual(result["status"], "differences", requirement)
            self.assertIn(expected, result["rules"], requirement)

        # Host-level items still produce nothing, however they are phrased.
        host_cases = [
            ("Containerization", "A dedicated partition should be mounted at /var/lib/docker"),
            ("Docker Auditing", "Audit rules must record access to /usr/bin/runc"),
            ("TLS Certificates", "The TLS CA certificate file must be owned by root"),
            ("Bind Mounts", "Host directories mounted into containers must be restricted"),
        ]
        for name, requirement in host_cases:
            with open("difference_names.txt", "w") as f:
                f.write(f"Names only in file 1:\n{name}\n")
            with open("difference_requirements.txt", "w") as f:
                f.write(f"Requirements only in file 1:\n{name},{requirement}\n")
            result = map_differences_to_rules()
            self.assertEqual(result["rules"], [], requirement)


    def test_run_hadolint(self):

        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        # A ZIP holding a root-level Dockerfile and one in a subfolder, both of
        # which break the rules the mapper selected above.
        with open("Dockerfile", "w") as f:
            f.write("FROM ubuntu:latest\n"
                    "USER root\n"
                    "RUN apt-get install -y curl\n")
        os.makedirs("app")
        with open(os.path.join("app", "Dockerfile"), "w") as f:
            f.write("FROM ubuntu:latest\n"
                    "WORKDIR /app\n"
                    "RUN apt-get install -y curl\n")
        with zipfile.ZipFile("dockerfiles.zip", "w") as zf:
            zf.write("Dockerfile", "Dockerfile")
            zf.write(os.path.join("app", "Dockerfile"), "app/Dockerfile")

        # The rule selection comes from the TEXT file the mapper writes, so that
        # file is produced first, exactly as the pipeline does it.
        mapped = map_differences_to_rules()
        self.assertEqual(mapped["status"], "differences")

        df = run_hadolint(hadolint_cmd=cmd)

        # A pandas DataFrame with one row per finding and the agreed columns.
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), ["FilePath", "Line", "Column", "RULEID",
                                            "Severity", "Message"])
        self.assertFalse(df.empty)

        # Both Dockerfiles were scanned, reported by their path inside the ZIP.
        self.assertEqual(set(df["FilePath"]), {"Dockerfile", "app/Dockerfile"})

        # Only the mapped rules are reported, even though these Dockerfiles break
        # several others (DL3009, DL3014, DL3027, DL4006 ...).
        self.assertTrue(set(df["RULEID"]) <= set(mapped["rules"]))

        # NO MAPPING FOUND / NO DIFFERENCES FOUND must fall back to a scan with
        # every rule available, including DL3057 which Hadolint ships disabled.
        with open("hadolint_rules.txt", "w") as f:
            f.write(NO_MAPPING + "\n")
        with open("Dockerfile", "w") as f:
            f.write("FROM ubuntu:20.04\n"
                    "RUN echo hi\n")
        all_rules = run_hadolint(hadolint_cmd=cmd)
        reported = set(all_rules["RULEID"])
        self.assertIn("DL3057", reported)          # off by default, switched on
        self.assertIn("DL3007", reported)          # `latest` tag
        self.assertIn("DL3008", reported)          # unpinned apt-get install
        # Rules outside the mapped set prove the scan was not restricted.
        self.assertFalse(reported <= set(mapped["rules"]))

        # The root-level Dockerfile must be picked up by DL3002 (last USER is root).
        root_rules = set(df[df["FilePath"] == "Dockerfile"]["RULEID"])
        self.assertIn("DL3002", root_rules)

        # A missing source or rule file is an error, not an empty result.
        with self.assertRaises(FileNotFoundError):
            run_hadolint(dockerfiles_source="nope.zip", hadolint_cmd=cmd)
        with self.assertRaises(FileNotFoundError):
            run_hadolint(rules_txt_path="nope.txt", hadolint_cmd=cmd)


    def test_run_hadolint_from_plain_folder(self):

        # The Dockerfiles are handed over unpacked, in the project folder itself,
        # so run_hadolint() must scan the current folder without a ZIP.
        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        with open("Dockerfile", "w") as f:
            f.write("FROM ubuntu:latest\nUSER root\nRUN apt-get install curl\n")
        os.makedirs("service")
        with open(os.path.join("service", "Dockerfile"), "w") as f:
            f.write("FROM ubuntu:latest\nWORKDIR /app\nRUN apt-get install curl\n")
        # Not a Dockerfile: must not be scanned.
        with open("notes.txt", "w") as f:
            f.write("FROM ubuntu:latest\n")

        mapped = map_differences_to_rules()
        self.assertEqual(mapped["status"], "differences")

        df = run_hadolint(hadolint_cmd=cmd)      # default source is "."

        self.assertEqual(set(df["FilePath"]), {"Dockerfile", "service/Dockerfile"})
        self.assertTrue(set(df["RULEID"]) <= set(mapped["rules"]))

        # A folder with no Dockerfiles in it is a clear error, not an empty result.
        os.makedirs("empty")
        with self.assertRaises(ValueError):
            run_hadolint(dockerfiles_source="empty", hadolint_cmd=cmd)


    def test_run_hadolint_batches_many_files(self):

        # The course dataset holds thousands of Dockerfiles. One Hadolint process
        # per file made that look hung (tens of ms of process startup each), so
        # files are batched: the result must still name every file correctly.
        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        from executor import _batch_paths, _MAX_BATCH_FILES

        paths = [f"svc{i}/Dockerfile" for i in range(_MAX_BATCH_FILES * 2 + 25)]
        self.assertEqual(len(_batch_paths(paths)), 3)
        self.assertEqual(sum(len(b) for b in _batch_paths(paths)), len(paths))
        self.assertEqual(_batch_paths([]), [])

        os.makedirs("many")
        expected = set()
        for i in range(250):
            folder = os.path.join("many", f"svc{i // 50}")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"Dockerfile{i}")
            with open(path, "w") as f:
                f.write("FROM ubuntu:latest\nUSER root\nRUN apt-get install curl\n")
            expected.add(os.path.relpath(path, ".").replace(os.sep, "/"))

        with open("hadolint_rules.txt", "w") as f:
            f.write(NO_MAPPING + "\n")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df = run_hadolint(dockerfiles_source="many", hadolint_cmd=cmd)

        # Every file is attributed to its own path, across all batches.
        self.assertEqual(set(df["FilePath"]), expected)
        self.assertEqual(df["FilePath"].nunique(), 250)

        # Progress is reported, so a slow run never looks hung again.
        printed = out.getvalue()
        self.assertIn("Scanning 250 Dockerfile(s)", printed)
        self.assertIn("250/250 files", printed)
        self.assertIn("2/2 calls", printed)

        # A bad timeout is rejected up front; progress can be silenced.
        with self.assertRaises(ValueError):
            run_hadolint(dockerfiles_source="many", hadolint_cmd=cmd, timeout=0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_hadolint(dockerfiles_source="many", hadolint_cmd=cmd, progress=False)
        self.assertEqual(out.getvalue(), "")


    def test_workers_knob_and_parallel_results_match_serial(self):

        # HADOLINT_WORKERS is the one knob a reader is meant to change, so it has
        # to be honoured, overridable, validated, and must not alter the results.
        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        self.assertEqual(HADOLINT_WORKERS, 8)
        self.assertEqual(_resolve_workers(), 8)
        self.assertEqual(_resolve_workers(1), 1)

        # The environment variable overrides the constant for a single run.
        os.environ[HADOLINT_WORKERS_ENV] = "3"
        try:
            self.assertEqual(_resolve_workers(), 3)
            self.assertEqual(_resolve_workers(2), 2)   # explicit argument wins
        finally:
            del os.environ[HADOLINT_WORKERS_ENV]

        for bad in (0, -1, "many", "1.5", 1.5, True, object()):
            with self.assertRaises(ValueError):
                _resolve_workers(bad)

        for i in range(120):
            os.makedirs("par", exist_ok=True)
            with open(os.path.join("par", f"Dockerfile{i}"), "w") as f:
                f.write("FROM ubuntu:latest\nUSER root\nRUN apt-get install curl\n")

        with open("hadolint_rules.txt", "w") as f:
            f.write("DL3002\nDL3008\n")

        with contextlib.redirect_stdout(io.StringIO()):
            serial = run_hadolint(dockerfiles_source="par", hadolint_cmd=cmd,
                                  workers=1)
            parallel = run_hadolint(dockerfiles_source="par", hadolint_cmd=cmd,
                                    workers=8)

        # Same rows in the same order regardless of how many processes ran, so a
        # parallel run is reproducible and diffable against a serial one.
        self.assertListEqual(serial.values.tolist(), parallel.values.tolist())
        self.assertEqual(len(parallel), 240)
        self.assertEqual(parallel.attrs["dockerfiles_scanned"], 120)

    def test_run_hadolint_isolates_crashing_dockerfile(self):

        # Hadolint is Haskell: a malformed Dockerfile makes it die with
        # "Data.Text...index: Index too large" and take the whole batch with it.
        # One bad file in 400,000 must not lose the other 399,999 findings.
        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        # A wrapper that crashes exactly when the poisoned file is in the call,
        # like the real binary does, and otherwise defers to the real Hadolint.
        poison = "svc2/Dockerfile666"
        wrapper = "crashing-hadolint.py"
        with open(wrapper, "w") as f:
            f.write(
                "import subprocess, sys\n"
                "args = sys.argv[1:]\n"
                "files = [a for a in args if not a.startswith('-')]\n"
                "if any(f.endswith('%s') for f in files):\n"
                "    sys.stderr.write('hadolint: Data.Text.Internal.Fusion.Common"
                ".index: Index too large\\n')\n"
                "    sys.stderr.write('CallStack (from HasCallStack):\\n')\n"
                "    sys.exit(1)\n"
                "sys.exit(subprocess.run([%r] + args).returncode)\n"
                % (poison.split('/')[-1], cmd)
            )
        # Run it through this interpreter rather than relying on the shebang:
        # Windows cannot execute a .py file directly, so `os.path.abspath(wrapper)`
        # alone is a FileNotFoundError / WinError 193 there.
        wrapper_cmd = [sys.executable, os.path.abspath(wrapper)]

        for i in range(300):
            folder = os.path.join("mixed", f"svc{i // 100}")
            os.makedirs(folder, exist_ok=True)
            name = "Dockerfile666" if i == 266 else f"Dockerfile{i}"
            with open(os.path.join(folder, name), "w") as f:
                f.write("FROM ubuntu:latest\nUSER root\n")

        with open("hadolint_rules.txt", "w") as f:
            f.write("DL3002\n")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df = run_hadolint(dockerfiles_source="mixed",
                              hadolint_cmd=wrapper_cmd)

        failures = df.attrs["failures"]
        self.assertEqual([p for p, _ in failures], [poison])
        self.assertIn("Index too large", failures[0][1])
        self.assertEqual(df.attrs["dockerfiles_scanned"], 299)

        # Every other file was still scanned and attributed.
        self.assertNotIn(poison, set(df["FilePath"]))
        self.assertEqual(df["FilePath"].nunique(), 299)
        self.assertTrue((df["RULEID"] == "DL3002").all())

        # And the skipped file is written out rather than silently dropped.
        path = write_failure_csv(failures, "failures.csv")
        self.assertEqual(path, "failures.csv")
        with open(path) as f:
            text = f.read()
        self.assertIn(poison, text)
        self.assertIn("Index too large", text)


    def test_out_of_scope_rules_are_dropped(self):

        # Task-3: "run the tool only on the rules that are in the TEXT file".
        # ShellCheck codes cannot be switched off with --ignore because RULES does
        # not enumerate them, so they are dropped from the results instead. A
        # Dockerfile that trips SC2086 and DL3008 must contribute only DL3008.
        cmd = hadolint_command()
        if cmd is None:
            self.skipTest("Hadolint is not installed; set HADOLINT or add it to PATH.")

        os.makedirs("scan", exist_ok=True)
        with open(os.path.join("scan", "Dockerfile"), "w") as f:
            # SC2086 (unquoted $x) and DL3008 (apt-get without a version pin).
            f.write("FROM ubuntu:20.04\n"
                    "USER app\n"
                    "RUN apt-get update && apt-get install -y curl $PKG\n")
        with open("hadolint_rules.txt", "w") as f:
            f.write("DL3008\n")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df = run_hadolint(dockerfiles_source="scan", hadolint_cmd=cmd)

        self.assertIn("DL3008", set(df["RULEID"]))
        self.assertNotIn("SC2086", set(df["RULEID"]))
        self.assertTrue(all(r.startswith("DL") for r in set(df["RULEID"])),
                        set(df["RULEID"]))
        self.assertGreater(df.attrs["out_of_scope_dropped"], 0)

        # And nothing out of scope reaches the deliverable.
        write_summary_csv(df, "results.csv")
        with open("results.csv") as f:
            rules = {line.split(",")[2] for line in f.read().splitlines()[1:]}
        self.assertEqual(rules, {"DL3008"})

        # NO MAPPING keeps every rule: the filter must not empty the results.
        with open("hadolint_rules.txt", "w") as f:
            f.write(NO_MAPPING + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            everything = run_hadolint(dockerfiles_source="scan", hadolint_cmd=cmd)
        self.assertEqual(everything.attrs["out_of_scope_dropped"], 0)
        self.assertIn("SC2086", set(everything["RULEID"]))


    def test_dockerfile_detection_ignores_source_files(self):

        # Running from the project folder means every .py, .txt, .zip and .pdf
        # sits next to the Dockerfiles. Only real Dockerfiles may be scanned,
        # otherwise Hadolint reports junk rows for the submission's own code.
        try:
            from .executor import _looks_like_dockerfile
        except ImportError:
            from executor import _looks_like_dockerfile

        real = {
            "Dockerfile": "FROM ubuntu:20.04\nRUN echo hi\n",
            "dockerfile": "FROM ubuntu:20.04\n",
            "Dockerfile.prod": "FROM ubuntu:20.04\n",
            "app.Dockerfile": "FROM ubuntu:20.04\n",
            "build": "FROM ubuntu:20.04 AS base\n",          # unnamed, sniffed
            "service": "# comment\n\nFROM arm64v8/ubuntu:20.04\n",
        }
        for name, content in real.items():
            with open(name, "w") as f:
                f.write(content)
            self.assertTrue(_looks_like_dockerfile(name), name)

        not_real = {
            "transformers.py": "from . import x\n",          # "from" != FROM clause
            "__init__.py": "from ._base import A, B\n",
            "main.py": "import sys\nfrom extractor import x\n",
            "notes.txt": "FROM ubuntu:latest\n",             # extension => not sniffed
            "dockerfiles.zip": "PK\x03\x04",
            "docker-cis-v0.pdf": "%PDF-1.4\n",
            "requirements.txt": "pandas\n",
        }
        for name, content in not_real.items():
            with open(name, "w") as f:
                f.write(content)
            self.assertFalse(_looks_like_dockerfile(name), name)

        # A zip of Dockerfiles is still recognised as an archive, not as a file.
        with zipfile.ZipFile("dockerfiles.zip", "w") as zf:
            zf.write("Dockerfile", "Dockerfile")
        self.assertFalse(_looks_like_dockerfile("dockerfiles.zip"))


    def test_refilter_results_csv(self):

        # A results CSV written before the restriction existed still carries the
        # ShellCheck rules, which --ignore cannot suppress. Re-filtering it has to
        # give exactly what a re-scan would: same rows kept, same counts.
        with open("hadolint_results.csv", "w", newline="") as f:
            f.write("FilePath,DefaultSeverity,RULEID,COUNT\n"
                    "a/Dockerfile,warning,DL3008,2\n"
                    "a/Dockerfile,info,SC2086,5\n"
                    "a/Dockerfile,ignore,DL3057,1\n"
                    "b/Dockerfile,error,DL3020,1\n")
        with open("hadolint_rules.txt", "w") as f:
            f.write("DL3008\nDL3020\n")

        self.assertEqual(refilter_results_csv("hadolint_results.csv",
                                              "hadolint_rules.txt", dry_run=True),
                         (2, 2))
        with open("hadolint_results.csv") as f:
            self.assertEqual(len(f.read().splitlines()), 5)      # dry run wrote nothing

        self.assertEqual(refilter_results_csv("hadolint_results.csv",
                                              "hadolint_rules.txt"), (2, 2))
        with open("hadolint_results.csv") as f:
            rows = f.read().splitlines()
        self.assertEqual(rows[0], "FilePath,DefaultSeverity,RULEID,COUNT")
        self.assertEqual(rows[1:], ["a/Dockerfile,warning,DL3008,2",
                                    "b/Dockerfile,error,DL3020,1"])

        # NO MAPPING means all rules are in scope: nothing may be dropped.
        with open("hadolint_rules.txt", "w") as f:
            f.write(NO_MAPPING + "\n")
        self.assertEqual(refilter_results_csv("hadolint_results.csv",
                                              "hadolint_rules.txt"), (2, 0))


    def test_write_summary_csv(self):

        df = pd.DataFrame([
            {"FilePath": "Dockerfile", "Line": 1, "Column": 1, "RULEID": "DL3008",
             "Severity": "warning", "Message": "Pin versions in apt get install."},
            {"FilePath": "Dockerfile", "Line": 3, "Column": 1, "RULEID": "DL3008",
             "Severity": "warning", "Message": "Pin versions in apt get install."},
            {"FilePath": "Dockerfile", "Line": 3, "Column": 1, "RULEID": "DL3002",
             "Severity": "warning", "Message": "Last USER should not be root"},
            {"FilePath": "app/Dockerfile", "Line": 1, "Column": 1, "RULEID": "DL3007",
             "Severity": "warning", "Message": "Using latest is prone to errors."},
        ])

        write_summary_csv(df)
        with open("hadolint_results.csv") as f:
            lines = [ln.strip() for ln in f if ln.strip()]

        # Header plus one line per (file, rule) pair, counts aggregated.
        self.assertEqual(lines[0], "FilePath,DefaultSeverity,RULEID,COUNT")
        self.assertIn("Dockerfile,warning,DL3002,1", lines)
        self.assertIn("Dockerfile,warning,DL3008,2", lines)
        self.assertIn("app/Dockerfile,warning,DL3007,1", lines)
        self.assertEqual(len(lines), 4)

        # An empty scan still writes a valid CSV with just the header.
        write_summary_csv(df.iloc[0:0])
        with open("hadolint_results.csv") as f:
            self.assertEqual(f.read().strip(), "FilePath,DefaultSeverity,RULEID,COUNT")

        # Type checking.
        with self.assertRaises(TypeError):
            write_summary_csv([])


if __name__ == "__main__":
    unittest.main()
