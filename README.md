# Secure Software Process Project

**COMP 5/6700 — Secure Software Process**

| | |
|---|---|
| **Names** | Courtney Lin, Nicholas Marden |
| **Banner IDs** | 904315203, 904289055 |
| **Emails** | cll0070@auburn.edu, nlm0021@auburn.edu |
| **LLM used** | Gemma-3-1B (`google/gemma-3-1b-it`, Hugging Face `transformers`) |

Detects the differences between two Docker CIS benchmark documents, maps those
differences to Hadolint rules, and runs Hadolint over a dataset of Dockerfiles.

---

## Quick start

```bash
pip install -r requirements.txt
huggingface-cli login            # read token; accept the licence at
                                 # https://huggingface.co/google/gemma-3-1b-it

python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf docker-cis-v2.pdf
```

That runs all five input combinations into `results/Input-1 … Input-5`. The
Dockerfile dataset (~397,000 files, half a gigabyte) is **not** in this
repository — see [Running](#running).

---

## Requirements

- Python 3.9+ (tested on 3.11 and 3.12)
- `pip install -r requirements.txt`
- [Hadolint](https://github.com/hadolint/hadolint) v2.12.0 on `PATH`, or set
  `HADOLINT` to the binary's path
- A Hugging Face **read token**: Gemma-3-1B is a gated model. `huggingface-cli
  login`, or `export HF_TOKEN=hf_xxx` (`$env:HF_TOKEN="hf_xxx"` on PowerShell).

The model (~2 GB) downloads on first run into `~/.cache/huggingface`. It uses the
GPU when there is room and falls back to the CPU otherwise; if you hit GPU memory
limits set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.

---

## Layout

```
Secure-Software-Process-Project/
├── main.py                        # one command runs Tasks 1-3
├── requirements.txt
├── PROMPT.md                      # the prompts given to the LLM
├── install.py                     # installs the post-merge git hook
├── Refilter Results.py            # re-apply the rule restriction to an old CSV
├── build_binary.py                # builds the Task-4 executable
├── ci/report.py                   # pass/fail table in the Actions summary
├── .github/workflows/tests.yml    # GitHub Action: runs the tests
├── githooks/post-merge            # dependency check after `git pull`
├── task1_extractor/
│   ├── extractor.py               # PDF reader, Gemma-3-1B call, KDE YAML output
│   ├── prompt_constructors.py     # zero-shot / few-shot / chain-of-thought
│   └── test_extractor.py
├── task2_comparator/
│   ├── comparator.py              # finds name and requirement differences
│   └── test_comparator.py
└── task3_executor/
    ├── executor.py                # maps differences to Hadolint rules, runs Hadolint
    └── test_executor.py
```

Each task folder is self-contained: its test file inserts its own directory on
`sys.path`, so the suites run from the project root or from inside the folder.

---

## Running

```bash
# three documents: all five input combinations (the assignment's requirement)
python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf docker-cis-v2.pdf

# a subset of combinations
python3 main.py *.pdf --pairs 1,4

# two documents: one pair, written to the current folder
python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf

# Dockerfiles somewhere else (folder or .zip)
python3 main.py *.pdf --dockerfiles /path/to/dokcerfiles
```

`main.py` looks for the dataset in `dockerfiles/`, `dokcerfiles/`,
`dockerfiles_zip/`, then the project folder. It is excluded by `.gitignore`.

### The five input combinations

| Run | Document 1 | Document 2 |
|-----|------------|------------|
| Input-1 | docker-cis-v0.pdf | docker-cis-v1.pdf |
| Input-2 | docker-cis-v0.pdf | docker-cis-v2.pdf |
| Input-3 | docker-cis-v1.pdf | docker-cis-v2.pdf |
| Input-4 | docker-cis-v1.pdf | docker-cis-v1.pdf |
| Input-5 | docker-cis-v2.pdf | docker-cis-v2.pdf |

Input-4 and Input-5 are the identical-document controls: no name or requirement
differences, so `hadolint_rules.txt` records `NO DIFFERENCES FOUND` and Hadolint
runs with every rule enabled.

---

## Task 1 — Extractor

`document_reader()` validates the path and extracts the PDF text, failing with a
clear `ValueError` on a scanned/image-only PDF rather than returning nothing.

`gemma_3_1b()` sends each document through **three prompt types** — zero-shot,
few-shot and chain-of-thought, all built in `prompt_constructors.py` — and asks
for the key data elements (KDEs) as YAML:

```yaml
Docker Daemon:
  name: Docker Daemon
  requirements:
    - Docker daemon must include the auditing configuration in daemon.json.
```

- One KDE may map to **many** requirements; requirements accumulate per element
  name instead of overwriting.
- Markdown fences and prose are stripped before the answer is parsed as YAML.
- Every prompt and raw answer goes to `llm-outputs.txt`, so a bad extraction can
  be traced to the exact call that produced it.

Output: `<doc>-kdes.yaml` per input document, plus `llm-outputs.txt`.

---

## Task 2 — Comparator

| Function | Compares | Output |
|---|---|---|
| `id_differences_in_names()` | CIS item titles | `difference_names.txt` |
| `id_differences_in_requirements()` | requirement text under each matching title | `difference_requirements.txt` |

Matching is paraphrase-tolerant, so a reworded requirement is reported as a
requirement difference rather than as a missing item.

---

## Task 3 — Executor

1. `map_differences_to_rules()` reads both difference files and selects the
   Hadolint rules that could express each difference (`-y`, pinned versions, not
   running as root, and so on), writing `hadolint_rules.txt`.
2. `run_hadolint()` scans the Dockerfile dataset and records every finding in
   `hadolint_results.csv` (`FilePath, DefaultSeverity, RULEID, COUNT` — one row
   per file/rule pair). A Dockerfile that crashes Hadolint is recorded in
   `hadolint_failures.csv`.

### Only the rules named in the TEXT file are reported

The task requires the tool to run "only on the rules that are in the TEXT file".
Hadolint has no `--only`, so every unmapped Dockerfile rule is switched off with
`--ignore`, one flag per rule, taken from the 66-rule table in `executor.py`
(code → default severity, extracted from Hadolint 2.12.0).

ShellCheck rules cannot be switched off that way: their codes (`SC2086`, `SC2028`,
… 165 of them in a full scan) are not in that table, so there is nothing to
enumerate and ignore. They are removed from the results after the scan instead,
inside `run_hadolint()`, whenever a mapping exists — otherwise roughly a sixth of
the CSV would be rules the TEXT file never named.

When the mapper returns `NO MAPPING FOUND` or `NO DIFFERENCES FOUND`, every rule
runs and nothing is dropped: that is what the task specifies for that case.

A CSV written before this restriction existed still carries those rules. Re-apply
it in place rather than re-scanning — the CSV is aggregated per
`(FilePath, RULEID)`, so filtering rows is arithmetically identical to a scan made
with the restriction in place, and takes seconds instead of 27 minutes:

```bash
python3 "Refilter Results.py" --dry-run           # report only
python3 "Refilter Results.py"                     # every results/Input-*/ folder
python3 "Refilter Results.py" results/Input-3
```

### Parallel Hadolint processes

The scan spawns one Hadolint process per batch of Dockerfiles. How many run at
once is the `HADOLINT_WORKERS` constant near the top of `task3_executor/executor.py`:

```python
HADOLINT_WORKERS = 8     # <-- change this number
```

| Value | When to use it |
|-------|----------------|
| `8` | default; a modern 8-core laptop |
| `4` | 4-core machine, or a slow/spinning disk |
| `1` | one at a time (easiest to follow in a debugger) |
| `16` | many-core machine; above the core count it only costs memory |

Override it for one run without editing the file:

```bash
HADOLINT_WORKERS=4 python3 main.py *.pdf                  # Linux/macOS
set HADOLINT_WORKERS=4 && python main.py *.pdf            # cmd
$env:HADOLINT_WORKERS=4; python main.py *.pdf             # PowerShell
```

Or from Python: `run_hadolint(..., workers=4)`.

### Scaling

Hadolint's own work per file is tiny; nearly all the time is process startup, so
workers help up to the core count.

| Change | Effect |
|---|---|
| one process per Dockerfile → batches of ~200 | ~54x fewer process spawns |
| 1 worker → 8 workers | up to ~8x, capped by cores |
| full dataset: 397,567 files, 7,294 calls | **26 min 39 s**, 2,230,179 findings |

Results are collected by batch index and concatenated in order, so
`hadolint_results.csv` is byte-identical with 1 worker or 8.

### Failure handling

A batch that exits non-zero with no JSON is **bisected**: the good files are kept
and only the offending Dockerfile is dropped, with its error recorded in
`hadolint_failures.csv`. Without this, one file that crashes Hadolint's parser
(`Data.Text.Internal.Fusion.Common.index: Index too large`) would discard the
findings of its whole batch. On the full dataset, 2 of 397,567 files crash.

---

## Task 4 — Delivery

### Tests

```bash
python3 -m pytest -q        # 25 tests: 10 extractor, 3 comparator, 12 executor
```

The six executor tests that invoke Hadolint itself skip when the binary is not on
`PATH`; the rest run without it.

### GitHub Action

`.github/workflows/tests.yml` runs on every push, every pull request, and on
manual dispatch: Ubuntu and Windows × Python 3.11 and 3.12. It installs Hadolint,
runs each task's suite as a separate step so a failure names the task, writes
JUnit XML per suite, and uploads that XML as a build artifact.

`ci/report.py` turns the XML into a pass/fail table in the run **Summary**,
naming any failing test, and fails the job when a suite is red or did not run.
`torch` and `transformers` are not installed in CI — `extractor.py` imports them
lazily, so the suites finish in seconds.

A GitHub Action cannot see a local `git pull`, so the workflow covers the
repository side and `githooks/post-merge` covers the developer's machine.

### Putting the project on GitHub (first time)

```bash
git init -b main
git add .
git commit -m "COMP 5/6700 secure software process project"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

On github.com: **Settings → General → Danger Zone → Change visibility → Public**
(the task requires a public repository), and **Actions → Enable workflow** if the
run did not start by itself. The workflow appears under **Actions** as *tests*;
open the run and its **Summary** for the pass/fail table.

Requirements this satisfies: public repository, a GitHub Action file with logs of
test-case execution, `requirements.txt`, and a binary buildable with
`python3 build_binary.py`.

### Post-merge hook

```bash
python3 install.py      # once per clone
```

`.git/hooks/post-merge` then runs after every `git pull` / `git merge`: it
reinstalls `requirements.txt` when that file changed or packages are missing,
warns if Hadolint is absent, and runs the tests so a bad merge is visible at once.

### Build the executable

```bash
python3 build_binary.py             # -> dist/SecureSoftwareProcess/
python3 build_binary.py --onefile   # single file
```

`build_binary.py` bundles torch, transformers and their data files, so the binary
runs on a machine with no Python installed:

```bash
dist/SecureSoftwareProcess/SecureSoftwareProcess docker-cis-v0.pdf docker-cis-v1.pdf docker-cis-v2.pdf
```

The Gemma weights are **not** bundled (re-downloadable, ~2 GB), so the first run
still fetches them with `HF_TOKEN`. PyInstaller cannot cross-compile: build on
Windows to get the `.exe`.

### Gain insight

Scanning 397,567 real Dockerfiles with every rule enabled produced **2,230,179
findings**, an average of 5.6 per file, and 90 of 91 KDEs were recovered from both
documents. Restricting the `v1 → v2` scan to the 15 mapped rules still left
**852,173 findings** across 482,542 file/rule pairs — the document-level
differences translate into rules that fire on real community Dockerfiles, not just
on paper. The two controls (Input-4, Input-5) produce zero mapped rules while still
scanning the dataset, which confirms the pipeline reports differences only when the
documents differ. The lesson for the process: a handful of changed CIS requirements
expands into a large amount of real-world non-compliance, which is why the mapping
has to be automated rather than reviewed by hand.

---

## Output files

| File | Contents |
|------|----------|
| `<doc>-kdes.yaml` | key data elements per input document |
| `llm-outputs.txt` | every prompt, prompt type and raw LLM output |
| `results/Input-N/difference_names.txt` | CIS items whose titles differ |
| `results/Input-N/difference_requirements.txt` | CIS items whose requirements differ |
| `results/Input-N/hadolint_rules.txt` | rules mapped from those differences |
| `results/Input-N/hadolint_results.csv` | every Hadolint finding |
| `results/Input-N/hadolint_failures.csv` | Dockerfiles Hadolint could not parse |

If no difference maps to a Dockerfile-expressible rule, `hadolint_rules.txt`
records `NO MAPPING FOUND` and Hadolint scans with all rules enabled.

---

## Troubleshooting

**Running it locally**

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'pypdf'` | a different interpreter from the one you installed into. Use `python3 -m pip install -r requirements.txt`; on Windows try `py -3 main.py` |
| `ImportError: cannot import name 'Protocol' from 'typing'` | Python 3.7 (pyenv 3.7.3); `pypdf` needs 3.9+. `pyenv global 3.12` |
| `torch.OutOfMemoryError: CUDA out of memory` | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, or run on CPU |
| `ValueError: No Dockerfiles found` | the dataset is not unpacked there; pass `--dockerfiles PATH` |
| `FileNotFoundError: Hadolint was not found` | install Hadolint, or set `HADOLINT=/path/to/hadolint` |
| Hadolint seems to hang | it is not hung: ~7,300 process spawns. Progress prints every 25 batches |

**GitHub Actions**

| Summary says | Real cause | Fix |
|---|---|---|
| all three **did not run** | the job died before the first test step; the report runs with `if: always()`, so it still prints after the job is broken | scroll up to the first red step — that is the bug, not the report |
| `Maximum call stack size exceeded` in `setup-python` | `cache: pip` globbed the workspace for requirements files and a committed dataset overflowed the Node stack | `cache-dependency-path: requirements.txt` (already set); never commit the dataset |
| `Node.js 20 is deprecated` | action major version too old | `checkout@v5`, `setup-python@v6`, `upload-artifact@v5` (already set) |
| `hadolint: command not found` | binary missing, or `$GITHUB_PATH` expected to apply within the same step | the Windows step calls it by full path; on Linux it installs to `/usr/local/bin` |
| Task-3 green but **Skipped = 6** | Hadolint missing, so the tests that invoke it skipped themselves | check the Hadolint install step |
| `curl: (23) Permission denied` on Linux | writing to `/usr/local/bin` without `sudo` | `sudo curl` + `sudo chmod` (already set) |
| Task-3 red **on Windows only**, `[WinError 193]` | a test double was a `.py` file run directly; Windows ignores the shebang | `run_hadolint(hadolint_cmd=...)` accepts a sequence, so the double runs as `[sys.executable, script]` (already set) |
| `failures.csv` paths use `\` on Windows | `os.path.join` uses the platform separator | failure paths are normalised to `/`, matching `FilePath` in the results CSV (already set) |
| `remote: error: GH001: Large files detected` | dataset or a generated CSV was committed | both are in `.gitignore`; `git rm --cached` anything that slipped in |
