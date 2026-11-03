''' 
Courtney Lin, Nicholas Marden
Task 1 - Extractor
'''

# ---------------------------------- #
#     File for Testing Extractor     #
# ---------------------------------- #

# One test case for each of the six functions.
# Run in terminal:  python test_extractor.py
#
# The tests do NOT need the real Gemma-3-1B model: gemma_3_1b() accepts an llm_fn
# argument, so the tests inject a fake LLM that returns canned YAML outputs.
# To run for real, see the example runner at the bottom of this file.

import os
import tempfile
import unittest

from extractor import (document_reader, gemma_3_1b, output_txt_collector, _chunk_text,
                       condense_cis_text, _extract_elements, _merge_elements,
                       _truncate)
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
    # without Gemma installed. Different output for the chain-of-thought prompt,
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
        self.doc2 = make_sample_pdf(self.tmp.name, "docker-cis-v2.pdf", [
            "Section 7 Logging: All containers must stream logs to a central server.",
            "Section 7.1 Logs must be retained for at least 365 days.",
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

    def test_chunk_text(self):
        # Short text stays in one chunk.
        self.assertEqual(_chunk_text("a\nb\nc", max_chars=100), ["a\nb\nc"])
        # Long text is split, no chunk exceeds the limit, and no content is lost.
        text = "\n".join(f"line {i}" for i in range(500))
        chunks = _chunk_text(text, max_chars=200)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 200 for c in chunks))
        self.assertEqual("\n".join(chunks), text)
        # One enormous line is hard-split.
        big = _chunk_text("x" * 450, max_chars=200)
        self.assertEqual([len(c) for c in big], [200, 200, 50])

    def test_condense_cis_text(self):
        raw = (
            "Table of Contents\n1.1.1 Ensure a thing is set (Manual) ........ 15\n"
            "Page 15 \nInternal Only - General \n"
            "1.1.1 Ensure a separate partition for containers has been created \n(Manual) \n"
            "Profile Applicability: \n\u2022  Level 1 - Docker - Linux \n"
            "Description: \nDocker stores data under /var/lib/docker. \n"
            "Rationale: \nIt could fill up. \n"
            "Audit: \nRun mountpoint. \n"
            "Remediation: \nYou should create a separate partition for /var/lib/docker. \n"
            "Default Value: \nNone. \n"
            "Page 16 \nInternal Only - General \n"
            "1.1.2 Ensure only trusted users control the daemon (Manual) \nProfile Applicability: \n"
            "Description: \nOnly trusted users. \nRemediation: \nRemove untrusted users from the docker group. \n"
            "Appendix: Summary Table 1.1.1 Ensure a separate partition 77 78 97 98"
        )
        out = condense_cis_text(raw)
        self.assertIn("1.1.1 Ensure a separate partition for containers has been created", out)
        self.assertIn("Remediation: You should create a separate partition", out)
        self.assertIn("1.1.2 Ensure only trusted users control the daemon", out)
        # Table of contents, rationale, audit, page headers and appendix numbers are gone.
        for dropped in ("Table of Contents", "Rationale", "It could fill up", "Run mountpoint",
                        "Internal Only", "Page 15", "77 78"):
            self.assertNotIn(dropped, out)
        # Text with no recommendations (like the small sample PDFs) is returned unchanged.
        self.assertEqual(condense_cis_text("Just some plain text."), "Just some plain text.")

    def test_extract_filters_junk_and_merge_dedupes(self):
        data = {
            "element1": {"name": "Element name", "requirements": ["req1", "req2"]},
            "element2": {"name": "Docker Swarm", "requirements": [
                "req1", "77", "Yes", "Configure the swarm manager to run in auto-lock mode.",
                "<one complete requirement sentence>",
                "Disable root login over SSH by setting PermitRootLogin to no"]},
            "element3": {"name": "Page Numbers", "requirements": ["1", "2", "3"]},
        }
        elements = _extract_elements(data)
        # Placeholder element, number-only element, placeholder/number/few-word/example requirements all dropped.
        self.assertEqual(elements, [{"name": "Docker Swarm", "requirements": [
            "Configure the swarm manager to run in auto-lock mode."]}])

        # Near-duplicate names and repeated requirements are merged into one KDE.
        merged = _merge_elements([
            [{"name": "Docker Daemon", "requirements": ["Use a non-root user."]}],
            [{"name": "daemon", "requirements": ["Use a non-root user", "Enable live restore."]}],
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged["element1"]["requirements"], ["Use a non-root user.", "Enable live restore."])

    def test_example_copies_dicts_and_duplicates(self):
        data = {
            "element1": {"name": "SSH Daemon Configuration", "requirements": [
                "Configure an SSH idle timeout is configured",
                "Set server_tokens to off in the web server configuration"]},
            "element2": {"name": "Logging", "requirements": [
                "Set Docker daemon log level to info.",
                {"Run the Docker daemon as below": 'dockerd --log-level="info"'}]},
        }
        elements = _extract_elements(data)
        # Reworded copies of the few-shot examples are dropped, along with the element they leave empty.
        self.assertEqual([e["name"] for e in elements], ["Logging"])
        # A requirement that YAML parsed as a one-key dict becomes one plain string.
        self.assertEqual(elements[0]["requirements"][1],
                         'Run the Docker daemon as below: dockerd --log-level="info"')

        # The same requirement under two KDE names is kept only under the first.
        merged = _merge_elements([[
            {"name": "Host Device Exposure", "requirements": ["You should not expose host devices to containers."]},
            {"name": "Device Permissions", "requirements": ["You should not expose host devices to containers."]},
        ]])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged["element1"]["name"], "Host Device Exposure")

        # Truncation happens at a sentence end, never mid-word.
        text = "First sentence is here. Second sentence is longer than the limit allows for sure."
        self.assertEqual(_truncate(text, 40), "First sentence is here.")
        self.assertFalse(_truncate("word " * 30, 42).endswith("wo"))

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

        results = gemma_3_1b(
            document_reader(self.doc0),
            document_reader(self.doc1),
            document_reader(self.doc2),
            doc1_name=os.path.basename(self.doc0),
            doc2_name=os.path.basename(self.doc1),
            doc3_name=os.path.basename(self.doc2),
            yaml_dir=self.tmp.name,
            llm_fn=mock_llm,
        )

        # One nested dictionary per document, keyed by the document file name.
        self.assertEqual(set(results.keys()),
                         {"docker-cis-v0.pdf", "docker-cis-v1.pdf", "docker-cis-v2.pdf"})
        v0 = results["docker-cis-v0.pdf"]
        self.assertIn("element1", v0)
        self.assertIn("name", v0["element1"])
        self.assertIn("requirements", v0["element1"])
        self.assertIsInstance(v0["element1"]["requirements"], list)

        # One KDE can map to multiple requirements.
        self.assertGreaterEqual(len(v0["element1"]["requirements"]), 1)

        # Three separate YAML files, named after the three input documents.
        yaml0 = os.path.join(self.tmp.name, "docker-cis-v0-kdes.yaml")
        yaml1 = os.path.join(self.tmp.name, "docker-cis-v1-kdes.yaml")
        yaml2 = os.path.join(self.tmp.name, "docker-cis-v2-kdes.yaml")
        self.assertTrue(os.path.isfile(yaml0))
        self.assertTrue(os.path.isfile(yaml1))
        self.assertTrue(os.path.isfile(yaml2))

        # Two documents (doc3_str=None) must still work.
        results_two = gemma_3_1b(
            document_reader(self.doc0),
            document_reader(self.doc1),
            None,
            doc1_name=os.path.basename(self.doc0),
            doc2_name=os.path.basename(self.doc1),
            yaml_dir=self.tmp.name,
            llm_fn=mock_llm,
        )
        self.assertEqual(set(results_two.keys()), {"docker-cis-v0.pdf", "docker-cis-v1.pdf"})

    # ----------------------------- #
    #  6. Test: output_txt_collector#
    # ----------------------------- #

    def test_output_txt_collector(self):
        # Running with no LLM calls recorded should raise.
        with self.assertRaises(ValueError):
            output_txt_collector(os.path.join(self.tmp.name, "empty.txt"), log=[])

        text0 = document_reader(self.doc0)
        text1 = document_reader(self.doc1)
        text2 = document_reader(self.doc2)

        # Reset the shared log so this test only counts its own LLM calls.
        # (In the real run the log keeps every call made during the session.)
        import extractor
        extractor.LLM_LOG.clear()

        gemma_3_1b(
            text0, text1, text2,
            doc1_name=os.path.basename(self.doc0),
            doc2_name=os.path.basename(self.doc1),
            doc3_name=os.path.basename(self.doc2),
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
        # Three documents x three prompt types = nine logged LLM calls.
        self.assertEqual(content.count("*LLM Name*"), 9)
        self.assertEqual(content.count("*Prompt Type"), 9)


if __name__ == "__main__":
    unittest.main()

    # ---------------------------------------------------------------- #
    #  Real run (needs Gemma-3-1B via Hugging Face, and the PDFs disk): #
    # ---------------------------------------------------------------- #
    # import extractor
    # text0 = document_reader("docker-cis-v0.pdf")
    # text1 = document_reader("docker-cis-v1.pdf")
    # text2 = document_reader("docker-cis-v2.pdf")
    # results = extractor.gemma_3_1b(
    #     text0, text1, text2,
    #     doc1_name="docker-cis-v0.pdf",
    #     doc2_name="docker-cis-v1.pdf",
    #     doc3_name="docker-cis-v2.pdf",
    # )
    # extractor.output_txt_collector("llm-outputs.txt")
    # print(results)
