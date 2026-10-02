'''
Courtney Lin, Nicholas Marden
Task 1 - Extractor - Runner

Usage:
    python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf

Prerequisites (one time):
    1) install Ollama:        https://ollama.com/download
    2) pull the model:        ollama pull gemma3:1b
    3) keep Ollama running    (the app, or `ollama serve`)
    4) pip install pypdf pyyaml requests

Outputs (in the current folder):
    docker-cis-v0-kdes.yaml   - KDEs for the first document
    docker-cis-v1-kdes.yaml   - KDEs for the second document
    llm-outputs.txt           - all LLM calls in the required format
'''

import sys
from extractor import document_reader, gemma_3_1b, output_txt_collector


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 main.py <document1.pdf> <document2.pdf>")
        print("Example: python3 main.py docker-cis-v0.pdf docker-cis-v1.pdf")
        sys.exit(1)

    doc1_path, doc2_path = sys.argv[1], sys.argv[2]

    # Input validation + text extraction (from extractor.py).
    doc1_str = document_reader(doc1_path)
    doc2_str = document_reader(doc2_path)

    # Run all three prompt types on both documents through Gemma-3-1B.
    results = gemma_3_1b(
        doc1_str, doc2_str,
        doc1_name=doc1_path,
        doc2_name=doc2_path,
        yaml_dir=".",
    )

    # Dump every LLM call to the TEXT file in the required format.
    txt_path = output_txt_collector("llm-outputs.txt")

    print(f"Saved: {doc1_path}-kdes.yaml".replace(".pdf-kdes", "-kdes"))
    print(f"Saved: {doc2_path}-kdes.yaml".replace(".pdf-kdes", "-kdes"))
    print(f"Saved: {txt_path}")
    for doc_name, kdes in results.items():
        print(f"\n{doc_name}: {len(kdes)} KDE(s) found")


if __name__ == "__main__":
    main()
