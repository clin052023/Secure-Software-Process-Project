# Prompt.md File
*Courtney Lin, Nicholas Marden*

**All prompts used during Task 1 (Extractor):**

The `{doc_text}` placeholder below is filled in at run time with the text
extracted from the input PDF by `document_reader()`. The YAML skeleton shown as
`{output_format}` in the actual prompts is:

```yaml
- element1:
    name: "Element name"
    requirements:
      - "req1"
      - "req2"
      - "req3"
- element2:
    name: "Element name"
    requirements:
      - "req1"
      - "req2"
```

## Zero-Shot Prompts

**Zero-Shot 1 — basic KDE extraction (used by `zero_shot()` in prompt_constructors.py):**

```text
Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.

Document:
"""
{doc_text}
"""

Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item).Output ONLY valid YAML with no preamble, markdown ticks, or commentary:
{output_format}
```

## Few-Shot Prompts

**Few-Shot 1 — two worked examples (used by `few_shot()` in prompt_constructors.py):**

```text
Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.

--- EXAMPLE 1 ---
Document Text:
"3.1 Access Control: All administrative accounts must enforce Multi-Factor Authentication (MFA). Passwords must be at least 16 characters long and changed every 90 days."

Output:
- element1:
    name: "Access Control"
    requirements:
    - "All administrative accounts must enforce Multi-Factor Authentication (MFA)"
    - "Passwords must be at least 16 characters long"
    - "Passwords must be changed every 90 days"
--- END EXAMPLE 1 ---

--- EXAMPLE 2 ---
Document Text:
"Section 5 - Data Encryption: Sensitive data at rest must use AES-256 encryption. Data in transit must be encrypted using TLS 1.3."

Output:
- element1:
    name: "Data Encryption"
    requirements:
    - "Sensitive data at rest must use AES-256 encryption"
    - "Data in transit must be encrypted using TLS 1.3"
--- END EXAMPLE 2 ---

Now, process the following document.

Document:
"""
{doc_text}
"""

Format the output strictly as valid YAML matching this structure from the examples above (incrementing element1, element2, etc. for each item).Output ONLY valid YAML with no preamble, markdown ticks, or commentary:
{output_format}
```

## Chain-of-Thought Prompts

**Chain-of-Thought 1 — reasoning before the YAML (used by `chain_of_thought()` in prompt_constructors.py):**

```text
Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.

Document:
"""
{doc_text}
"""

Step 1: Before writing the final YAML output, output your reasoning as you think through the document. List each major security section you find and summarize its key rules.

Step 2: After your step-by-step breakdown, output the divider "--- YAML ---" followed ONLY by the final valid YAML.

Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item).After the divider, output strictly valid YAML with no markdown ticks, or commentary:
{output_format}
```
