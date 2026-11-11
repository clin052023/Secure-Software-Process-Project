'''
Courtney Lin, Nicholas Marden
COMP 5/6120 - Secure Software Process
Project Runner (Tasks 1-3 in one command)

Usage:
    python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf docker-cis-v2.pdf
    python3 main.py <doc> <doc>                       # two documents only

Each run does:

    Task-1  Extract KDEs from every input document with Gemma-3-1B and three
            prompt types -> <doc>-kdes.yaml (one per document) + llm-outputs.txt
    Task-2  Compare each pair of documents (the five input combinations)
            -> results/Input-N/difference_names.txt
            -> results/Input-N/difference_requirements.txt
    Task-3  Map the differences to Hadolint rules and run Hadolint over the
            Dockerfile dataset -> results/Input-N/hadolint_rules.txt
            -> results/Input-N/hadolint_results.csv
            -> results/Input-N/hadolint_failures.csv (only if some file crashed)

The five input combinations are:

    Input-1: docker-cis-v0.pdf  vs  docker-cis-v1.pdf
    Input-2: docker-cis-v0.pdf  vs  docker-cis-v2.pdf
    Input-3: docker-cis-v1.pdf  vs  docker-cis-v2.pdf
    Input-4: docker-cis-v1.pdf  vs  docker-cis-v1.pdf
    Input-5: docker-cis-v2.pdf  vs  docker-cis-v2.pdf

Options:
    --dockerfiles PATH   folder or .zip holding the Dockerfile dataset.
                         Default: ./dockerfiles, ./dokcerfiles, or the current
                         folder, whichever holds Dockerfiles first.
    --pairs 1,3          run only the given input combinations (default: all).

Prerequisites (one time):
    1)  pip install -r requirements.txt
    2) accept the Gemma license (gated model):
        https://huggingface.co/google/gemma-3-1b-it
    3) use your Hugging Face read token, either with `huggingface-cli login`
       or by setting the HF_TOKEN environment variable
    4) the model (~2 GB) downloads on the first run, then is cached locally
    5) Hadolint must be installed and on PATH (or set the HADOLINT variable):
        https://github.com/hadolint/hadolint#install
'''

import os
import sys

from task1_extractor.extractor import (document_reader, gemma_3_1b,
                                       output_txt_collector)
from task2_comparator import comparator
from task3_executor import executor


# The five input combinations required by the assignment, by document number.
INPUT_COMBINATIONS = {
    1: (0, 1),
    2: (0, 2),
    3: (1, 2),
    4: (1, 1),
    5: (2, 2),
}


def _parse_args(argv):
    # Splits argv into the PDF paths and the two optional switches.
    docs, dockerfiles, pairs = [], None, None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--dockerfiles":
            if i + 1 >= len(argv):
                raise SystemExit("--dockerfiles needs a path")
            dockerfiles = argv[i + 1]
            i += 2
            continue
        if arg == "--pairs":
            if i + 1 >= len(argv):
                raise SystemExit("--pairs needs a list, e.g. --pairs 1,3")
            pairs = [int(p) for p in argv[i + 1].replace(" ", "").split(",") if p]
            i += 2
            continue
        docs.append(arg)
        i += 1
    return docs, dockerfiles, pairs


def _default_dockerfiles_source():
    # The dataset is usually unzipped into the project folder under one of these
    # names (the assignment's archive is called "dokcerfiles" after unpacking).
    for candidate in ("dockerfiles", "dokcerfiles", "dockerfiles_zip"):
        if os.path.isdir(candidate) and executor._find_dockerfiles(candidate):
            return candidate
    return "."


def _run_pair(doc_a, doc_b, label, out_dir, dockerfiles_source):
    # Task-2 + Task-3 for one pair of documents. Each pair gets its own folder
    # because comparator.py and executor.py write fixed file names.
    os.makedirs(out_dir, exist_ok=True)
    previous_cwd = os.getcwd()
    os.chdir(out_dir)
    try:
        yaml_a = os.path.join(previous_cwd, _yaml_name(doc_a))
        yaml_b = os.path.join(previous_cwd, _yaml_name(doc_b))
        doc1_yaml, doc2_yaml = comparator.load_files(yaml_a, yaml_b)

        comparator.id_differences_in_names(doc1_yaml, doc2_yaml)
        comparator.id_differences_in_requirements(doc1_yaml, doc2_yaml)

        mapping = executor.map_differences_to_rules("difference_names.txt",
                                                    "difference_requirements.txt",
                                                    "hadolint_rules.txt")
        print(f"  {label}: mapping = {mapping['status']}")

        findings = executor.run_hadolint(
            rules_txt_path="hadolint_rules.txt",
            dockerfiles_source=os.path.abspath(
                os.path.join(previous_cwd, dockerfiles_source)),
        )
        csv_path = executor.write_summary_csv(findings, "hadolint_results.csv")
        print(f"  {label}: {csv_path} ({len(findings)} finding(s) across "
              f"{findings['FilePath'].nunique()} Dockerfile(s))")
        dropped = findings.attrs.get("out_of_scope_dropped") or 0
        if dropped:
            print(f"  {label}: {dropped} finding(s) outside the TEXT file's rules "
                  f"were dropped (Task-3: run the tool only on those rules)")

        failures = findings.attrs.get("failures") or []
        if failures:
            executor.write_failure_csv(failures, "hadolint_failures.csv")
            print(f"  {label}: {len(failures)} Dockerfile(s) skipped "
                  f"(see hadolint_failures.csv)")
        return {"mapping": mapping["status"],
                "findings": len(findings),
                "dockerfiles": int(findings['FilePath'].nunique()),
                "failures": len(failures)}
    finally:
        os.chdir(previous_cwd)


def _yaml_name(pdf_path):
    # 'docker-cis-v0.pdf' -> 'docker-cis-v0-kdes.yaml'
    return os.path.basename(pdf_path).replace(".pdf", "-kdes.yaml")


def main(argv=None):
    docs, dockerfiles, pairs = _parse_args(sys.argv[1:] if argv is None else argv)

    if len(docs) not in (2, 3):
        print("Usage: python3 main.py <doc>.pdf <doc>.pdf [<doc>.pdf] "
              "[--dockerfiles PATH] [--pairs 1,3]")
        print("Example: python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf "
              "docker-cis-v2.pdf")
        return 1

    # Input validation happens in document_reader() for every document up front,
    # so a bad path fails before the model is loaded.
    texts = [document_reader(path) for path in docs]

    print(f"Task-1: extracting KDEs from {len(docs)} document(s) with "
          f"Gemma-3-1B (3 prompt types each)")

    # gemma_3_1b() takes up to three documents; pass the third only if present.
    if len(texts) == 3:
        results = gemma_3_1b(texts[0], texts[1], texts[2],
                             doc1_name=docs[0], doc2_name=docs[1],
                             doc3_name=docs[2], yaml_dir=".")
    else:
        results = gemma_3_1b(texts[0], texts[1],
                             doc1_name=docs[0], doc2_name=docs[1], yaml_dir=".")

    txt_path = output_txt_collector("llm-outputs.txt")
    for path in docs:
        print(f"Saved: {_yaml_name(path)}")
    print(f"Saved: {txt_path}")
    for doc_name, kdes in results.items():
        print(f"  {os.path.basename(doc_name)}: {len(kdes)} KDE(s)")

    # Task-2 + Task-3 for each requested input combination.
    if len(docs) < 3:
        print("Only two documents supplied: running one pair in the current folder.")
        chosen = {0: (0, 1)}
        label = f"{os.path.basename(docs[0])} vs {os.path.basename(docs[1])}"
        _run_pair(docs[0], docs[1], label, ".", dockerfiles or ".")
        return 0

    dockerfiles_source = dockerfiles or _default_dockerfiles_source()
    selected = pairs or sorted(INPUT_COMBINATIONS)
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    print(f"Task-2/3: Dockerfile dataset = {dockerfiles_source}")
    summary = {}
    for number in selected:
        if number not in INPUT_COMBINATIONS:
            raise SystemExit(f"Unknown input combination: {number} "
                             f"(expected 1-5)")
        a, b = INPUT_COMBINATIONS[number]
        label = f"Input-{number}: {os.path.basename(docs[a])} vs " \
                f"{os.path.basename(docs[b])}"
        print(f"\n{label}")
        summary[number] = _run_pair(docs[a], docs[b], label,
                                    os.path.join(results_dir, f"Input-{number}"),
                                    dockerfiles_source)

    print("\n" + "-" * 70)
    for number in sorted(summary):
        row = summary[number]
        print(f"Input-{number}: mapping={row['mapping']} "
              f"findings={row['findings']} dockerfiles={row['dockerfiles']} "
              f"skipped={row['failures']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
