''' 
Courtney Lin, Nicholas Marden
Task 1 - Extractor
'''

# ---------------------------------- #
#     File for Testing Extractor     #
# ---------------------------------- #

# One test case for each of the six functions.
# Run in terminal:  python extractor_test_cases.py
#
# The tests do NOT need the real Gemma-3-1B model: gemma_3_1b() accepts an llm_fn
# argument, so the tests inject a fake LLM that returns canned YAML outputs.
# To run for real, see the example runner at the bottom of this file.

import os
import tempfile
import unittest

from extractor import document_reader, gemma_3_1b, output_txt_collector
from prompt_constructors import zero_shot, few_shot, chain_of_thought

# run in terminal: pip install fpdf2
from fpdf import FPDF


def make_sample_pdf(dir_path, name, lines):
    # Builds a small but valid PDF containing the given lines of text.
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in lines:
        pdf.multi_cell(190, 8, line)
    path = os.path.join(dir_path, name)
    pdf.output(path)
    return path


def mock_llm(prompt):
    # A fake Gemma-3-1B that returns a plausible YAML answer, so the tests can run
    # without Ollama installed. Different output for the chain-of-thought prompt,
    # because that prompt asks for reasoning followed by a "--- YAML ---" divider.
    if "--- YAML ---" in prompt:
        return (
            "Step 1: The document covers access control and password policy.\n\n"
            "--- YAML ---\n"
            '- element1:\n'
            '    name: "Access Control"\n'
            '    requirements:\n'
            '      - "All administrative accounts must enforce Multi-Factor Authentication (MFA)"\n'
            '      - "Passwords must be at least 16 characters long"\n'
        )
    return (
        '- element1:\n'
        '    name: "Access Control"\n'
        '    requirements:\n'
        '      - "All administrative accounts must enforce Multi-Factor Authentication (MFA)"\n'
        '- element2:\n'
        '    name: "Password Policy"\n'
        '    requirements:\n'
        '      - "Passwords must be at least 16 characters long"\n'
        '      - "Passwords must be changed every 90 days"\n'
    )


class TestExtractorFunctions(unittest.TestCase):

    def setUp(self):
        # Fresh temp folder + sample PDFs for each test.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.doc0 = make_sample_pdf(self.tmp.name, "docker-cis-v0.pdf", [
            "Section 3.1 Access Control: All administrative accounts must enforce MFA.",
            "Section 3.2 Passwords: Passwords must be at least 16 characters long.",
        ])
        self.doc1 = make_sample_pdf(self.tmp.name, "docker-cis-v1.pdf", [
            "Section 5 Data Encryption: Sensitive data at rest must use AES-256 encryption.",
            "Section 5.1 Data in transit must be encrypted using TLS 1.3.",
        ])

    # ----------------------------- #
    #  1. Test: document_reader     #
    # ----------------------------- #

    def test_document_reader(self):
        # Valid PDF -> text is read back out.
        text = document_reader(self.doc0)
        self.assertIsInstance(text, str)
        self.assertIn("administrative accounts must enforce MFA", text)
        self.assertIn("at least 16 characters long", text)

        # Input validation: missing file.
        with self.assertRaises(FileNotFoundError):
            document_reader(os.path.join(self.tmp.name, "does-not-exist.pdf"))

        # Input validation: wrong extension.
        bad_ext = os.path.join(self.tmp.name, "not-a-pdf.txt")
        with open(bad_ext, "w") as f:
            f.write("hello")
        with self.assertRaises(ValueError):
            document_reader(bad_ext)

        # Input validation: .pdf extension but not a real PDF (bad header).
        bad_hdr = os.path.join(self.tmp.name, "fake.pdf")
        with open(bad_hdr, "wb") as f:
            f.write(b"this is not really a pdf at all")
        with self.assertRaises(ValueError):
            document_reader(bad_hdr)

    # ----------------------------- #
    #  2. Test: zero_shot           #
    # ----------------------------- #

    def test_zero_shot(self):
        prompt = zero_shot("All data must be encrypted at rest.")
        # Output must be a string (per the assignment).
        self.assertIsInstance(prompt, str)
        # The document text must be inside the prompt.
        self.assertIn("All data must be encrypted at rest.", prompt)
        # The prompt must ask for the YAML structure.
        self.assertIn("element1", prompt)
        self.assertIn("requirements", prompt)

    # ----------------------------- #
    #  3. Test: few_shot            #
    # ----------------------------- #

    def test_few_shot(self):
        prompt = few_shot("All data must be encrypted at rest.")
        self.assertIsInstance(prompt, str)
        self.assertIn("All data must be encrypted at rest.", prompt)
        # A few-shot prompt must contain worked examples to imitate.
        self.assertIn("EXAMPLE 1", prompt)
        self.assertIn("EXAMPLE 2", prompt)
        self.assertIn("element1", prompt)

    # ----------------------------- #
    #  4. Test: chain_of_thought    #
    # ----------------------------- #

    def test_chain_of_thought(self):
        prompt = chain_of_thought("All data must be encrypted at rest.")
        self.assertIsInstance(prompt, str)
        self.assertIn("All data must be encrypted at rest.", prompt)
        # A CoT prompt must ask for step-by-step reasoning plus the YAML divider.
        self.assertIn("Step 1", prompt)
        self.assertIn("--- YAML ---", prompt)

    # ----------------------------- #
    #  5. Test: gemma_3_1b          #
    # ----------------------------- #

    def test_gemma_3_1b(self):
        text0 = document_reader(self.doc0)
        text1 = document_reader(self.doc1)

        results = gemma_3_1b(
            text0, text1,
            doc1_name=os.path.basename(self.doc0),
            doc2_name=os.path.basename(self.doc1),
            yaml_dir=self.tmp.name,
            llm_fn=mock_llm,
        )

        # One nested dictionary per document, keyed by the document file name.
        self.assertEqual(set(results.keys()), {"docker-cis-v0.pdf", "docker-cis-v1.pdf"})
        v0 = results["docker-cis-v0.pdf"]
        self.assertIn("element1", v0)
        self.assertIn("name", v0["element1"])
        self.assertIn("requirements", v0["element1"])
        self.assertIsInstance(v0["element1"]["requirements"], list)

        # One KDE can map to multiple requirements.
        self.assertGreaterEqual(len(v0["element1"]["requirements"]), 1)

        # Two separate YAML files, named after the two input documents.
        yaml0 = os.path.join(self.tmp.name, "docker-cis-v0-kdes.yaml")
        yaml1 = os.path.join(self.tmp.name, "docker-cis-v1-kdes.yaml")
        self.assertTrue(os.path.isfile(yaml0))
        self.assertTrue(os.path.isfile(yaml1))

    # ----------------------------- #
    #  6. Test: output_txt_collector#
    # ----------------------------- #

    def test_output_txt_collector(self):
        # Running with no LLM calls recorded should raise.
        with self.assertRaises(ValueError):
            output_txt_collector(os.path.join(self.tmp.name, "empty.txt"), log=[])

        text0 = document_reader(self.doc0)
        text1 = document_reader(self.doc1)

        # Reset the shared log so this test only counts its own LLM calls.
        # (In the real run the log keeps every call made during the session.)
        import extractor
        extractor.LLM_LOG.clear()

        gemma_3_1b(
            text0, text1,
            doc1_name=os.path.basename(self.doc0),
            doc2_name=os.path.basename(self.doc1),
            yaml_dir=self.tmp.name,
            llm_fn=mock_llm,
        )

        txt_path = os.path.join(self.tmp.name, "llm-outputs.txt")
        output_txt_collector(txt_path)

        with open(txt_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIsInstance(content, str)
        # The required four labels, in the required order.
        self.assertEqual(content.index("*LLM Name*"), 0)
        self.assertLess(content.index("*LLM Name*"), content.index("*Prompt Used*"))
        self.assertLess(content.index("*Prompt Used*"), content.index("*Prompt Type"))
        self.assertLess(content.index("*Prompt Type"), content.index("*LLM Output*"))
        # Two documents x three prompt types = six logged LLM calls.
        self.assertEqual(content.count("*LLM Name*"), 6)
        self.assertEqual(content.count("*Prompt Type"), 6)


if __name__ == "__main__":
    unittest.main()

    # ------------------------------------------------------------------ #
    #  Real run (needs Ollama + gemma3:1b, and two of the three PDFs on disk):    #
    # ------------------------------------------------------------------ #
    # import extractor
    # text0 = document_reader("docker-cis-v0.pdf")
    # text1 = document_reader("docker-cis-v1.pdf")
    # results = extractor.gemma_3_1b(
    #     text0, text1,
    #     doc1_name="docker-cis-v0.pdf",
    #     doc2_name="docker-cis-v1.pdf",
    # )
    # extractor.output_txt_collector("llm-outputs.txt")
    # print(results)