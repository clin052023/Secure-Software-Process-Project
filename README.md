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

That runs all five input combinations into `results/Input-1 … Input-5`. 

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
