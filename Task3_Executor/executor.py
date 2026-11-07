''' 
Courtney Lin, Nicholas Marden
Task 3 - Executor
'''

# ------------------------------------- #
#          - Executor File -            #
#      Rule Mapping and Hadolint        #
# ------------------------------------- #

# Four functions:
#   read_difference_files()      - takes the two TEXT files from Task-2
#   map_differences_to_rules()   - CIS differences -> Hadolint rules (TEXT file)
#   run_hadolint()               - runs Hadolint on dockerfiles.zip (pandas DataFrame)
#   write_summary_csv()          - FilePath, DefaultSeverity, RULEID, COUNT (CSV file)

import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd


# --------------------------- #
#     Hadolint Rule Table     #
# --------------------------- #

# Every rule hadolint v2.12.0 knows, with its DEFAULT severity and message, taken
# from the tool's own source (src/Hadolint/Rule/DLxxxx.hs). The default severity
# is what write_summary_csv() reports as DefaultSeverity. Severity "ignore" means
# the rule is off unless it is switched on explicitly (DL3057).

RULES = {
    "DL1001": ("ignore", "Please refrain from using inline igore pragmas `# hadolint ignore=DLxxxx`."),
    "DL3000": ("error", "Use absolute WORKDIR"),
    "DL3001": ("info", "For some bash commands it makes no sense running them in a Docker container like `ssh`, `vim`, `shutdown`, `service`, `ps`, `free`, `top`, `kill`, `mount`, `ifconfig`"),
    "DL3002": ("warning", "Last USER should not be root"),
    "DL3003": ("warning", "Use WORKDIR to switch to a directory"),
    "DL3004": ("error", "Do not use sudo as it leads to unpredictable behavior. Use a tool like gosu to enforce root"),
    "DL3005": ("error", "Do not use apt-get dist-upgrade"),
    "DL3006": ("warning", "Always tag the version of an image explicitly"),
    "DL3007": ("warning", "Using latest is prone to errors if the image will ever update. Pin the version explicitly to a release tag"),
    "DL3008": ("warning", "Pin versions in apt get install. Instead of `apt-get install <package>` use `apt-get install <package>=<version>`"),
    "DL3009": ("info", "Delete the apt-get lists after installing something"),
    "DL3010": ("info", "Use `ADD` for extracting archives into an image"),
    "DL3011": ("error", "Valid UNIX ports range from 0 to 65535"),
    "DL3012": ("error", "Multiple `HEALTHCHECK` instructions"),
    "DL3013": ("warning", "Pin versions in pip. Instead of `pip install <package>` use `pip install <package>==<version>` or `pip install --requirement <requirements file>`"),
    "DL3014": ("warning", "Use the `-y` switch to avoid manual input `apt-get -y install <package>`"),
    "DL3015": ("info", "Avoid additional packages by specifying `--no-install-recommends`"),
    "DL3016": ("warning", "Pin versions in npm. Instead of `npm install <package>` use `npm install <package>@<version>`"),
    "DL3018": ("warning", "Pin versions in apk add. Instead of `apk add <package>` use `apk add <package>=<version>`"),
    "DL3019": ("info", "Use the `--no-cache` switch to avoid the need to use `--update` and remove `/var/cache/apk/*` when done installing packages"),
    "DL3020": ("error", "Use COPY instead of ADD for files and folders"),
    "DL3021": ("error", "COPY with more than 2 arguments requires the last argument to end with /"),
    "DL3022": ("warning", "`COPY --from` should reference a previously defined `FROM` alias"),
    "DL3023": ("error", "`COPY --from` cannot reference its own `FROM` alias"),
    "DL3024": ("error", "FROM aliases (stage names) must be unique"),
    "DL3025": ("warning", "Use arguments JSON notation for CMD and ENTRYPOINT arguments"),
    "DL3026": ("error", "Use only an allowed registry in the FROM image"),
    "DL3027": ("warning", "Do not use apt as it is meant to be a end-user tool, use apt-get or apt-cache instead"),
    "DL3028": ("warning", "Pin versions in gem install. Instead of `gem install <gem>` use `gem install <gem>:<version>`"),
    "DL3029": ("warning", "Do not use --platform flag with FROM"),
    "DL3030": ("warning", "Use the -y switch to avoid manual input `yum install -y <package`"),
    "DL3032": ("warning", "`yum clean all` missing after yum command."),
    "DL3033": ("warning", "Specify version with `yum install -y <package>-<version>`."),
    "DL3034": ("warning", "Non-interactive switch missing from `zypper` command: `zypper install -y`"),
    "DL3035": ("warning", "Do not use `zypper dist-upgrade`."),
    "DL3036": ("warning", "`zypper clean` missing after zypper use."),
    "DL3037": ("warning", "Specify version with `zypper install -y <package>=<version>`."),
    "DL3038": ("warning", "Use the -y switch to avoid manual input `dnf install -y <package`"),
    "DL3040": ("warning", "`dnf clean all` missing after dnf command."),
    "DL3041": ("warning", "Specify version with `dnf install -y <package>-<version>`."),
    "DL3042": ("warning", "Avoid use of cache directory with pip. Use `pip install --no-cache-dir <package>`"),
    "DL3043": ("error", "`ONBUILD`, `FROM` or `MAINTAINER` triggered from within `ONBUILD` instruction."),
    "DL3044": ("error", "Do not refer to an environment variable within the same `ENV` statement where it is defined."),
    "DL3045": ("warning", "`COPY` to a relative destination without `WORKDIR` set."),
    "DL3046": ("warning", "`useradd` without flag `-l` and high UID will result in excessively large Image."),
    "DL3047": ("info", "Avoid use of wget without progress bar. Use `wget --progress=dot:giga <url>`. Or consider using `-q` or `-nv` (shorthands for `--quiet` or `--no-verbose`)."),
    "DL3048": ("style", "Invalid label key."),
    "DL3049": ("info", "Label `` is missing."),
    "DL3050": ("info", "Superfluous label(s) present."),
    "DL3051": ("warning", "label `` is empty."),
    "DL3052": ("warning", "Label `` is not a valid URL."),
    "DL3053": ("warning", "Label `` is not a valid time format - must be conform to RFC3339."),
    "DL3054": ("warning", "Label `` is not a valid SPDX identifier."),
    "DL3055": ("warning", "Label `` is not a valid git hash."),
    "DL3056": ("warning", "Label `` does not conform to semantic versioning."),
    "DL3057": ("ignore", "`HEALTHCHECK` instruction missing."),
    "DL3058": ("warning", "Label `` is not a valid email format - must be conform to RFC5322."),
    "DL3059": ("info", "Multiple consecutive `RUN` instructions. Consider consolidation."),
    "DL3060": ("info", "`yarn cache clean` missing after `yarn install` was run."),
    "DL3061": ("error", "Invalid instruction order. Dockerfile must begin with `FROM`, `ARG` or comment."),
    "DL4000": ("error", "MAINTAINER is deprecated"),
    "DL4001": ("warning", "Either use Wget or Curl but not both"),
    "DL4003": ("warning", "Multiple `CMD` instructions found. If you list more than one `CMD` then only the last `CMD` will take effect"),
    "DL4004": ("error", "Multiple `ENTRYPOINT` instructions found. If you list more than one `ENTRYPOINT` then only the last `ENTRYPOINT` will take effect"),
    "DL4005": ("warning", "Use SHELL to change the default shell"),
    "DL4006": ("warning", "Set the SHELL option -o pipefail before RUN with a pipe in it. If you are using /bin/sh in an alpine image or if your shell is symlinked to busybox then consider explicitly setting your SHELL to /bin/ash, or disable this check"),}


# ------------------------------- #
#     CIS Difference -> Rule Map  #
# ------------------------------- #

# Only CIS Docker Benchmark items that can actually be seen in a Dockerfile are
# mapped here. Host- and daemon-level items (auditd rules, a separate partition
# for /var/lib/docker, docker group membership, TLS files on the host, bind mounts
# of host directories) have no Dockerfile counterpart and are left out on
# purpose: Hadolint only analyses Dockerfiles, so mapping them would produce
# rules that can never fire.
#
# Each entry: (CIS item, CIS title, keywords searched for in the Task-2 output,
# Hadolint rules the item maps to).

CIS_RULE_MAP = [
    ("4.1", "Ensure a user for the container has been created",
     ["user for the container", "container user", "non-root", "root user",
      "run as root", "useradd", "adduser", "user id", "user uid"],
     ["DL3002", "DL3046"]),

    ("4.2", "Ensure that containers use trusted base images",
     ["trusted base image", "base image", "trusted registr", "allowed registr",
      "latest tag", "image tag", "pin the version of the image", "image version"],
     ["DL3006", "DL3007", "DL3026", "DL3029"]),

    ("4.3", "Ensure that unnecessary packages are not installed in the container",
     ["unnecessary package", "additional package", "no-install-recommends",
      "package cache", "apt-get lists", "clean all", "clean up",
      "consecutive run", "minimize the number of layers"],
     ["DL3009", "DL3015", "DL3019", "DL3042", "DL3047", "DL3059"]),

    ("4.6", "Ensure that HEALTHCHECK instructions have been added to container images",
     ["healthcheck", "health check"],
     ["DL3012", "DL3057"]),

    ("4.7", "Ensure update instructions are not used alone in the Dockerfile",
     ["dist-upgrade", "upgrade instruction", "update instructions",
      "run update", "apt-get upgrade"],
     ["DL3005", "DL3035"]),

    ("4.9", "Ensure that COPY is used instead of ADD in Dockerfiles",
     ["copy instead of add", "use copy", "add instruction", "add command",
      "add for archives"],
     ["DL3010", "DL3020"]),

    ("4.11", "Ensure verified packages are only installed",
     ["pin versions", "pin the version", "pinned version", "verified package",
      "signed package", "package version", "specific version"],
     ["DL3008", "DL3013", "DL3016", "DL3018", "DL3028", "DL3033", "DL3037",
      "DL3041"]),

    ("5.7", "Ensure privileged ports are not mapped within containers",
     ["privileged port", "port range", "exposed port", "expose instruction",
      "port 0 to 65535"],
     ["DL3011"]),
]

# CIS items recognised in the differences that have no Dockerfile counterpart.
# They never produce a rule (the README limits mapping to CIS items that relate to
# Dockerfiles); map_differences_to_rules() reports them back so the caller can
# explain why a run ended in NO MAPPING FOUND. Each entry:
# (CIS item, title, keywords, why it cannot be checked).
CIS_UNMAPPABLE = [
    ("1.2", "Ensure a separate partition for containers has been created",
     ["separate partition", "partition for containers"],
     "host filesystem layout, not a Dockerfile instruction"),

    ("1.6", "Ensure auditing is configured for Docker files and directories",
     ["auditing is configured", "add a rule for the /etc/docker",
      "add a rule for the /etc/containerd", "add a rule for the /etc/default/docker",
      "add a rule for the /etc/sysconfig/docker", "add a rule for the /usr/bin/"],
     "auditd rules live on the host (audit rules, /etc/audit/*), Hadolint does "
     "not parse them"),

    ("1.7", "Ensure auditing is configured for the Docker daemon",
     ["auditing is configured for the docker daemon"],
     "daemon configuration (daemon.json) lives on the host"),

    ("3.1", "Ensure that the Docker daemon configuration is protected",
     ["mapping of sensitive directories", "host to container volumes",
      "sensitive director"],
     "bind mounts are chosen at `docker run` time, not in a Dockerfile"),

    ("5.1", "Ensure that the TLS CA certificate file is owned by root",
     ["tls ca certificate file", "tlscacert"],
     "certificate files are on the host filesystem, not in an image"),

    ("5.2", "Ensure that the TLS CA certificate file permissions are 444",
     ["permissions of 444", "tlscert"],
     "certificate file permissions are on the host filesystem"),
]

NO_DIFFERENCES = "NO DIFFERENCES FOUND"
NO_MAPPING = "NO MAPPING FOUND"


# ---------------------------------- #
#     TEXT Files from Task-2         #
# ---------------------------------- #

def _validate_txt_path(path, label):
    # Same validation style as document_reader() in extractor.py.
    if not isinstance(path, str) or not path.strip():
        raise TypeError(f"{label} must be a non-empty file path string.")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{label} not found: {path}")
    if not path.lower().endswith(".txt"):
        raise ValueError(f"Invalid File Extension: '{path}'. {label} must be a TEXT file.")


def _parse_difference_txt(path, collect_requirements):
    # Parses one TEXT file written by comparator.py:
    #   names        -> "Names only in file 1:" / "Names only in file 2:" then one name per line
    #   requirements -> "Requirements only in file 1:" / "... file 2:" then NAME,REQU per line
    file1, file2 = [], []
    section = None

    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            low = line.lower()

            # comparator.py reports "NO DIFFERENCES ..." when nothing differs.
            if low.startswith("no difference"):
                continue

            if line.endswith(":"):
                if "only in file 1" in low:
                    section = file1
                elif "only in file 2" in low:
                    section = file2
                else:
                    raise ValueError(f"'{path}' line {lineno}: unknown section header '{line}'.")
                continue

            if section is None:
                raise ValueError(f"'{path}' line {lineno}: entry before any section header.")

            if collect_requirements:
                name, sep, req = line.partition(",")
                if not sep or not name.strip() or not req.strip():
                    raise ValueError(
                        f"'{path}' line {lineno}: expected 'NAME,REQU', got '{line}'."
                    )
                section.append((name.strip(), req.strip()))
            else:
                section.append(line)

    return {"file1": file1, "file2": file2}


def read_difference_files(names_path="difference_names.txt",
                          requirements_path="difference_requirements.txt"):
    # Takes the two TEXT files produced by Task-2 and returns their content plus
    # a flag saying whether any difference was reported at all.
    _validate_txt_path(names_path, "Element names file")
    _validate_txt_path(requirements_path, "Element requirements file")

    names = _parse_difference_txt(names_path, collect_requirements=False)
    reqs = _parse_difference_txt(requirements_path, collect_requirements=True)

    # Any entry in any section means a difference was reported. A file that only
    # says "NO DIFFERENCES ..." parses to no entries, so it flags False.
    has_differences = bool(
        names["file1"] or names["file2"] or reqs["file1"] or reqs["file2"]
    )

    return {
        "names": {"file1": names["file1"], "file2": names["file2"]},
        "requirements": {"file1": reqs["file1"], "file2": reqs["file2"]},
        "has_differences": has_differences,
    }


# ---------------------------------- #
#     Differences -> Hadolint Rules  #
# ---------------------------------- #

# Words that carry no topic information, ignored when comparing a difference
# against a CIS keyword phrase.
_STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "at", "by", "with", "and",
    "or", "is", "are", "be", "been", "must", "should", "shall", "will", "can",
    "may", "not", "no", "any", "all", "each", "that", "this", "it", "its",
    "as", "if", "when", "than", "instead", "use", "used", "using", "make",
    "sure", "ensure", "container", "containers", "docker", "dockerfile",
}


def _content_words(text):
    # Lower-cases, splits on anything non-alphanumeric, and drops stopwords.
    # "COPY instead of ADD" -> {"copy", "add"}
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _phrase_hit(phrase, haystack_words, haystack_lower):
    # A keyword phrase counts as a hit when every one of its content words
    # appears somewhere in the difference text, in any order. The 1B model
    # paraphrases freely ("COPY must be used instead of ADD" rather than
    # "COPY instead of ADD"), so exact substrings miss real mappings; matching
    # on content words survives the rewording. Exact substrings are still tried
    # first, because a single-token keyword like "healthcheck" is more precise.
    if phrase in haystack_lower:
        return True
    needed = _content_words(phrase)
    return bool(needed) and needed <= haystack_words


def _match_cis_items(data):
    # Searches every difference reported by Task-2 for the keywords of each
    # Dockerfile-related CIS item. One difference can match several CIS items and
    # one CIS item maps to several Hadolint rules, so a single difference can end
    # up producing a whole set of rules.
    matches = []

    items = [(name, "") for name in data["names"]["file1"] + data["names"]["file2"]]
    items += list(data["requirements"]["file1"]) + list(data["requirements"]["file2"])

    for name, req in items:
        haystack = f"{name} {req}".lower()
        haystack_words = _content_words(haystack)

        for cis_id, cis_title, keywords, rule_codes in CIS_RULE_MAP:
            hit = next((k for k in keywords if _phrase_hit(k, haystack_words, haystack)), None)
            if hit is None:
                continue
            matches.append({
                "name": name,
                "requirement": req,
                "cis": f"CIS Docker {cis_id}",
                "cis_title": cis_title,
                "keyword": hit,
                "rules": list(rule_codes),
            })

    return matches


def _match_unmappable(data):
    # CIS items that appear in the differences but cannot be checked in a
    # Dockerfile. Returned as (CIS label, title, why) triples, de-duplicated.
    items = [name for name in data["names"]["file1"] + data["names"]["file2"]]
    items += [f"{name} {req}" for name, req in
              data["requirements"]["file1"] + data["requirements"]["file2"]]

    found = []
    for cis_id, cis_title, keywords, why in CIS_UNMAPPABLE:
        texts = [(t.lower(), _content_words(t)) for t in items]
        if any(_phrase_hit(k, words, low) for low, words in texts for k in keywords):
            found.append((f"CIS Docker {cis_id}", cis_title, why))
    return found


def map_differences_to_rules(names_path="difference_names.txt",
                             requirements_path="difference_requirements.txt",
                             output_path="hadolint_rules.txt"):
    # Writes the TEXT file that drives the Hadolint run. Its content is one of:
    #   NO DIFFERENCES FOUND                 - Task-2 reported no differences
    #   NO MAPPING FOUND                     - differences exist, none map to a rule
    #   DLRULE,severity,message              - one line per mapped rule
    #
    # Returns a dict with the status, the rule IDs, and the individual matches.
    data = read_difference_files(names_path, requirements_path)

    if not data["has_differences"]:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(NO_DIFFERENCES + "\n")
        return {"status": "no_differences", "rules": [], "matches": [],
                "unmappable": []}

    matches = _match_cis_items(data)
    unmappable = _match_unmappable(data)

    if not matches:
        # Differences exist, but not one of them can be checked in a Dockerfile,
        # so the README's second outcome applies. run_hadolint() reacts to this
        # file by scanning with every rule available.
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(NO_MAPPING + "\n")
        return {"status": "no_mapping", "rules": [], "matches": [],
                "unmappable": unmappable}

    # One line per rule: ID first so run_hadolint() can read it back, then the
    # default severity and the rule message so the file stays human readable.
    rule_ids = sorted({code for m in matches for code in m["rules"]})
    with open(output_path, "w", encoding="utf-8") as f:
        for code in rule_ids:
            severity, message = RULES.get(code, ("unknown", ""))
            f.write(f"{code},{severity},{message}\n")

    return {"status": "differences", "rules": rule_ids, "matches": matches,
            "unmappable": unmappable}


# ------------------------------------- #
#     Hadolint Execution -> DataFrame   #
# ------------------------------------- #

def _read_rule_selection(rules_txt_path):
    # Returns (rule_ids, restrict). restrict=False means "run every rule".
    if not os.path.isfile(rules_txt_path):
        raise FileNotFoundError(f"Rule file not found: {rules_txt_path}")

    with open(rules_txt_path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    # Tolerate comment lines so a hand-edited rule list still loads; the
    # generated file never writes them.
    lines = [ln for ln in lines if not ln.startswith("#")]

    if not lines or lines[0] in (NO_DIFFERENCES, NO_MAPPING):
        return [], False

    codes = []
    for line in lines:
        code = line.split(",", 1)[0].strip()
        if not code.startswith("DL"):
            raise ValueError(f"'{rules_txt_path}' is not a rule list: unexpected line '{line}'.")
        codes.append(code)
    return codes, True


def _selection_args(rule_ids):
    # Hadolint has no "--only" flag, so the complement is ignored instead: every
    # rule that is not selected gets --ignore. Rules whose default severity is
    # "ignore" (DL3057) are switched on by overriding their severity.
    selected = set(rule_ids)
    args = []
    for code in sorted(RULES):
        if code in selected or RULES[code][0] == "ignore":
            continue
        args += ["--ignore", code]
    for code in sorted(selected):
        if RULES.get(code, ("",))[0] == "ignore":
            args += ["--warning", code]
    return args


# A Dockerfile by name: "Dockerfile", "Dockerfile.dev", "app.Dockerfile", ...
# Deliberately NOT a bare startswith("dockerfile"), which would also match
# "dockerfiles.zip" and every other "dockerfile..." artefact sitting in the folder.
_DOCKERFILE_NAME = re.compile(r"^dockerfile([._-][a-z0-9][a-z0-9._-]*)?$")


# The only instruction that can legally open a Dockerfile, in full-line form.
# Requiring the whole line to match is what keeps source files out: a Python file
# whose first line is "from . import x" has the token FROM, but is not a FROM
# clause, and scanning source files would put junk rows in every results CSV.
_FROM_LINE = re.compile(r"^from\s+[\w./:@${}-]+(\s+as\s+\w+)?$", re.IGNORECASE)


def _looks_like_dockerfile(path):
    base = os.path.basename(path).lower()
    if _DOCKERFILE_NAME.match(base) or base.endswith((".dockerfile", ".docker")):
        return True
    # Fallback for unnamed variants ("build", "production"): sniff only files with
    # no extension, and only accept one that reads as a Dockerfile.
    if os.path.splitext(base)[1]:
        return False
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for _ in range(40):
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                return bool(_FROM_LINE.match(line))
    except OSError:
        return False
    return False


# Folders that never hold the Dockerfiles being graded; skipping them keeps a
# scan of the whole project folder (the default "dockerfiles_source") fast.
_SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "node_modules",
              "results", ".venv", "venv", "env"}


def _find_dockerfiles(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in filenames:
            path = os.path.join(dirpath, name)
            if _looks_like_dockerfile(path):
                found.append(path)
    return sorted(found)


def _resolve_hadolint(hadolint_cmd=None):
    # Honours an explicit argument first, then $HADOLINT, then PATH. Without this
    # a binary installed outside PATH (or the one the tests point at) could not
    # be used, and the failure would only show up as a bare FileNotFoundError.
    if hadolint_cmd:
        return hadolint_cmd
    if os.environ.get("HADOLINT"):
        return os.environ["HADOLINT"]
    found = shutil.which("hadolint")
    if found:
        return found
    raise FileNotFoundError(
        "Hadolint was not found. Install it (https://github.com/hadolint/hadolint) "
        "and put it on PATH, or set the HADOLINT environment variable."
    )


def _find_dockerfile_archive(folder):
    # Returns the first .zip in `folder` that contains a Dockerfile, or None.
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in entries:
        path = os.path.join(folder, name)
        if not name.lower().endswith(".zip") or not os.path.isfile(path):
            continue
        try:
            with zipfile.ZipFile(path) as zf:
                if any(_looks_like_dockerfile(n) for n in zf.namelist()):
                    return path
        except (zipfile.BadZipFile, OSError):
            continue
    return None


# Windows caps a command line at 32,767 characters, and long paths eat that fast.
# Batches are small enough to stay well inside the limit while still amortising
# process startup over dozens of files.
_MAX_BATCH_FILES = 200
_MAX_BATCH_CHARS = 8000

# ===========================================================================
#   >>>  HOW MANY HADOLINT PROCESSES RUN AT THE SAME TIME  <<<
#
#   CHANGE THIS NUMBER if the scan is too slow or your machine struggles.
#
#     8  = default; the speed-up is capped by your CPU core count
#     1  = one process at a time (old behaviour, easiest to read progress)
#     4  = a safe choice on a 4-core laptop or with a spinning disk
#     16 = only on a machine with many cores; more than the core count
#          gains nothing and just adds memory pressure
#
#   Example (4,000 Dockerfiles): 1 worker 10.4 s, 2 workers 8.7 s on a 2-core
#   machine -- the ceiling is the hardware, not this number.
#
#   Nothing else needs to change: every other part of the pipeline reads
#   this value. You can also override it for one run without editing this
#   file: run_hadolint(..., workers=4) or set the environment variable
#   HADOLINT_WORKERS=4.
# ===========================================================================
HADOLINT_WORKERS = 8

# Environment variable that overrides HADOLINT_WORKERS for a single run.
HADOLINT_WORKERS_ENV = "HADOLINT_WORKERS"


def _resolve_workers(workers=None):
    # Turn "not given / given / env var" into a positive integer.
    if workers is None:
        workers = os.environ.get(HADOLINT_WORKERS_ENV) or HADOLINT_WORKERS
    if isinstance(workers, bool):          # True/False are not worker counts
        raise ValueError(f"workers must be a whole number, got {workers!r}.")
    if isinstance(workers, float) and not workers.is_integer():
        raise ValueError(f"workers must be a whole number, got {workers!r}.")
    try:
        workers = int(workers)
    except (TypeError, ValueError):
        raise ValueError(f"workers must be a whole number, got {workers!r}.")
    if workers < 1:
        raise ValueError(f"workers must be at least 1, got {workers}.")
    return workers


def _batch_paths(paths):
    # Splits Dockerfile paths into groups that fit in one Hadolint invocation.
    batches, current, size = [], [], 0
    for path in paths:
        cost = len(path) + 3          # quoting and separating space
        if current and (len(current) >= _MAX_BATCH_FILES
                        or size + cost > _MAX_BATCH_CHARS):
            batches.append(current)
            current, size = [], 0
        current.append(path)
        size += cost
    if current:
        batches.append(current)
    return batches


def run_hadolint(rules_txt_path="hadolint_rules.txt",
                 dockerfiles_source=".",
                 hadolint_cmd=None,
                 timeout=900,
                 progress=True,
                 workers=None):
    # Runs Hadolint over every Dockerfile found under dockerfiles_source (a folder,
    # ".", or a ZIP, in case the Dockerfiles are shipped as an archive) using the
    # rules named in the TEXT file from map_differences_to_rules().
    # Returns a pandas DataFrame with one row per finding.
    hadolint_cmd = _resolve_hadolint(hadolint_cmd)
    rule_ids, restrict = _read_rule_selection(rules_txt_path)

    if not isinstance(dockerfiles_source, str) or not dockerfiles_source.strip():
        raise TypeError("dockerfiles_source must be a non-empty path string.")
    if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
        raise ValueError("timeout must be a positive number of seconds, or None.")

    cleanup = None
    if zipfile.is_zipfile(dockerfiles_source):
        cleanup = tempfile.mkdtemp(prefix="dockerfiles-")
        with zipfile.ZipFile(dockerfiles_source) as zf:
            members = zf.namelist()
            if progress:
                print(f"Extracting {len(members)} entr(ies) from "
                      f"'{os.path.basename(dockerfiles_source)}'...", flush=True)
            zf.extractall(cleanup)
        root = cleanup
    elif os.path.isdir(dockerfiles_source):
        root = dockerfiles_source
    else:
        raise FileNotFoundError(
            f"Dockerfile source not found: {dockerfiles_source} "
            "(expected a folder or a ZIP file)."
        )

    try:
        if progress:
            print(f"Looking for Dockerfiles under '{dockerfiles_source}'...", flush=True)
        dockerfiles = _find_dockerfiles(root)

        # The course ships the Dockerfiles as dockerfiles.zip. If the folder holds
        # the archive rather than the unpacked files, scan the archive instead of
        # failing: that is the layout the README describes.
        if not dockerfiles and os.path.isdir(root):
            archive = _find_dockerfile_archive(root)
            if archive:
                cleanup_from_archive = tempfile.mkdtemp(prefix="dockerfiles-")
                if progress:
                    print(f"Found '{os.path.basename(archive)}'; extracting...",
                          flush=True)
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(cleanup_from_archive)
                archive_files = _find_dockerfiles(cleanup_from_archive)
                if archive_files:
                    if cleanup:
                        shutil.rmtree(cleanup, ignore_errors=True)
                    cleanup, root, dockerfiles = (cleanup_from_archive,
                                                  cleanup_from_archive,
                                                  archive_files)
                else:
                    shutil.rmtree(cleanup_from_archive, ignore_errors=True)

        if not dockerfiles:
            raise ValueError(
                f"No Dockerfiles found in '{dockerfiles_source}'. Task-3 needs the "
                "course Dockerfile dataset: download dockerfiles.zip from the link in "
                "the README (Task-3) and put the .zip, or its unpacked contents, in "
                "the project folder. The three docker-cis-v*.pdf files are only the "
                "requirements documents for Task-1."
            )

        args = [hadolint_cmd, "--no-fail", "--no-color", "-f", "json"]
        if restrict:
            args += _selection_args(rule_ids)
        else:
            # NO DIFFERENCES FOUND / NO MAPPING FOUND means a scan with every rule
            # available. DL3057 ships switched off by default, so it is turned on
            # explicitly, otherwise "all rules" would silently skip it.
            args += ["--warning", "DL3057"]

        # Hadolint accepts many files in one call and tags each finding with its
        # "file", so the whole dataset is scanned in a few processes instead of
        # one per file. Spawning per file is what made a few-thousand-file
        # dataset look hung: on Windows each spawn costs tens of milliseconds.
        failures = []
        batches = _batch_paths(dockerfiles)
        workers = _resolve_workers(workers)
        workers = min(workers, len(batches))
        total_files = len(dockerfiles)

        if progress:
            print(f"Scanning {total_files} Dockerfile(s) in {len(batches)} "
                  f"Hadolint call(s), {workers} process(es) at a time "
                  f"(HADOLINT_WORKERS = {HADOLINT_WORKERS})...", flush=True)

        # Each batch is independent, so they are handed to a pool of worker
        # threads. Hadolint runs in a subprocess either way, so threads (not
        # processes) are the right tool: the time is spent waiting on Hadolint,
        # not in Python. Results are stored per batch index and concatenated in
        # order afterwards, so the CSV is byte-identical whatever the ordering.
        started = time.time()
        per_batch = [None] * len(batches)
        state = {"finished": 0, "files": 0, "rows": 0, "batches": 0}
        print_lock = threading.Lock()

        def scan(index):
            return index, _scan_batch(args, batches[index], timeout, failures, root)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(scan, i): i for i in range(len(batches))}
            for future in as_completed(futures):
                index, findings = future.result()
                per_batch[index] = findings

                with print_lock:
                    state["finished"] += 1
                    state["files"] += len(batches[index])
                    state["rows"] += len(findings)
                    state["batches"] += 1

                    if progress and (state["finished"] == len(batches)
                                     or state["finished"] % 25 == 0):
                        elapsed = time.time() - started
                        done = state["files"]
                        rate = done / elapsed if elapsed > 0 else 0
                        eta = (total_files - done) / rate if rate > 0 else 0
                        extra = f", {len(failures)} unreadable" if failures else ""
                        eta_text = (f", ~{_format_duration(eta)} left"
                                    if eta >= 1 else "")
                        print(f"  {done}/{total_files} files "
                              f"({state['finished']}/{len(batches)} calls, "
                              f"{_format_duration(elapsed)} elapsed{eta_text}): "
                              f"{state['rows']} finding(s){extra}", flush=True)

        rows = [row for findings in per_batch for row in findings]

        if failures and progress:
            print(f"\n{len(failures)} Dockerfile(s) crashed Hadolint and were "
                  "skipped (listed in hadolint_failures.csv).", flush=True)
            for path, message in failures[:10]:
                print(f"  {os.path.relpath(path, root)}: {message}")
            if len(failures) > 10:
                print(f"  ... and {len(failures) - 10} more")
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)

    frame = pd.DataFrame(rows, columns=["FilePath", "Line", "Column", "RULEID",
                                        "Severity", "Message"])
    # Attached so a partial scan is never silently presented as a complete one.
    frame.attrs["failures"] = [(os.path.relpath(path, root).replace(os.sep, "/"),
                                message) for path, message in failures]
    frame.attrs["dockerfiles_scanned"] = len(dockerfiles) - len(failures)
    return frame


# Hadolint is Haskell; when it hits a bad input it dies with an uncaught
# exception rather than a diagnostic. These are the shapes that shows up in.
_HADOLINT_CRASH_MARKERS = ("Index too large", "CallStack", "Prelude.",
                           "Data.Text", "Non-exhaustive patterns", "Irrefutable")


def _hadolint_error(result):
    # Returns a message when this Hadolint run produced no usable answer, else None.
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode == 0:
        return None
    if stdout:
        try:
            json.loads(stdout)             # findings were produced alongside the noise
            return None
        except json.JSONDecodeError:
            pass
    if any(marker in stderr for marker in _HADOLINT_CRASH_MARKERS):
        return stderr.splitlines()[0][:200] or "Hadolint crashed"
    return stderr[:200] or f"Hadolint exited with code {result.returncode}"


def _scan_batch(args, batch, timeout, failures, root):
    # Runs Hadolint on one batch and returns its findings. A batch that makes
    # Hadolint crash or hang is split in half and retried, so one malformed
    # Dockerfile out of four hundred thousand costs that one file instead of the
    # whole run. Only a single file that fails on its own is recorded as skipped.
    try:
        result = subprocess.run(args + batch, capture_output=True, text=True,
                                timeout=timeout)
        error = _hadolint_error(result)
    except subprocess.TimeoutExpired:
        error = f"timed out after {timeout}s"
    except OSError as e:
        raise RuntimeError(f"Could not run Hadolint: {e}") from e

    if error is None:
        try:
            findings = json.loads((result.stdout or "[]").strip() or "[]")
        except json.JSONDecodeError as e:
            error = f"invalid JSON ({e})"

    if error is None:
        rows = []
        for finding in findings:
            reported = finding.get("file") or ""
            if reported:
                rel = os.path.relpath(
                    reported if os.path.isabs(reported) else os.path.join(root, reported),
                    root).replace(os.sep, "/")
            else:
                rel = ""
            rows.append({
                "FilePath": rel,
                "Line": finding.get("line"),
                "Column": finding.get("column"),
                "RULEID": finding.get("code", ""),
                "Severity": finding.get("level", ""),
                "Message": (finding.get("message") or "").strip(),
            })
        return rows

    if len(batch) == 1:
        failures.append((batch[0], error))
        return []

    middle = len(batch) // 2
    return (_scan_batch(args, batch[:middle], timeout, failures, root)
            + _scan_batch(args, batch[middle:], timeout, failures, root))


def _format_duration(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def write_failure_csv(failures, csv_path="hadolint_failures.csv"):
    # Lists Dockerfiles Hadolint could not process, so they can be reported to the
    # course staff or excluded, instead of vanishing from the results.
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["FilePath", "Error"])
        writer.writeheader()
        for path, message in failures:
            writer.writerow({"FilePath": path, "Error": message})
    return csv_path


def write_summary_csv(df, csv_path="hadolint_results.csv"):
    # Aggregates the scan results to FilePath, DefaultSeverity, RULEID, COUNT.
    # DefaultSeverity is the rule's own default severity (RULES), not whatever the
    # scan reported, so an inline "# hadolint ignore" cannot change it.
    if not isinstance(df, pd.DataFrame):
        raise TypeError("write_summary_csv() expects a pandas DataFrame.")
    missing = {"FilePath", "RULEID"} - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing column(s): {', '.join(sorted(missing))}.")

    reported = {}
    if "Severity" in df.columns and not df.empty:
        reported = (df.groupby("RULEID")["Severity"]
                      .agg(lambda s: s.mode().iloc[0]).to_dict())

    rows = []
    if not df.empty:
        counts = df.groupby(["FilePath", "RULEID"]).size()
        for (file_path, rule_id), count in counts.items():
            severity = RULES.get(rule_id, (reported.get(rule_id, ""), ""))[0]
            rows.append({
                "FilePath": file_path,
                "DefaultSeverity": severity,
                "RULEID": rule_id,
                "COUNT": int(count),
            })

    rows.sort(key=lambda r: (r["FilePath"], r["RULEID"]))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["FilePath", "DefaultSeverity",
                                               "RULEID", "COUNT"])
        writer.writeheader()
        writer.writerows(rows)

    return csv_path
