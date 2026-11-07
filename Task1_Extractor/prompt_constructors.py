''' 
Courtney Lin, Nicholas Marden
Task 1 - Extractor
'''

# ---------------------------------- #
#     Prompt Generator Functions     #
# ---------------------------------- #

# Since each document needs to be saved into their own individual YAML files, each function 
# will be called twice to process two documents instead of calling each function once to process 
# both documents at the same time. This makes things a bit easier to manage.

# Format for Gemma-3-1b to follow for the desired output.
# The placeholders are written as <descriptions> (not as "req1", "req2") so a small model has
# nothing that looks like real content to copy; extractor.py also drops any <...> leftovers.
output_format = """
- element1:
    name: "<name of a security component or configuration area>"
    requirements:
      - "<one complete requirement sentence>"
      - "<another complete requirement sentence>"
- element2:
    name: "<name of a different component or area>"
    requirements:
      - "<one complete requirement sentence>"
"""

# What the document looks like and what a KDE is. Shared by all three prompts so they stay consistent.
# (extractor.py condenses the benchmark PDFs to numbered recommendations with a Description
# and a Remediation before sending them, so this is what the model actually receives.)
task_description = (
    "The text below contains numbered security recommendations from a security benchmark. "
    "Each one has a Description and a Remediation.\n"
    "Identify the Key Data Elements (KDEs): the components or configuration areas that the "
    "recommendations apply to (for example a daemon, a configuration file, a network, or an image). "
    "For each KDE, list the security requirements that apply to it as short, complete sentences "
    "based on the recommendations. Use only information from the document, and do not copy the examples. "
    "If the text contains no security requirements, output exactly: []\n\n"
)

# ------------------------------------------------------------------ #
#  Worked examples for the few-shot prompt (deliberately NOT Docker)  #
# ------------------------------------------------------------------ #
# The requirement strings are kept in a list so extractor.py can discard them if the
# model copies them into its answer instead of reading the real document.

EXAMPLE_TEXT_1 = (
    "2.1 Ensure SSH root login is disabled\n"
    "Description: Logging in directly as root removes accountability for administrative actions.\n"
    "Remediation: Set PermitRootLogin to no in /etc/ssh/sshd_config and restart the SSH service.\n\n"
    "2.2 Ensure SSH idle timeout is configured\n"
    "Description: Idle sessions left open can be hijacked.\n"
    "Remediation: Set ClientAliveInterval to 300 or less in /etc/ssh/sshd_config."
)

EXAMPLE_TEXT_2 = (
    "4.1 Ensure only modern TLS versions are enabled\n"
    "Description: Older TLS versions have known weaknesses.\n"
    "Remediation: Set ssl_protocols to TLSv1.2 TLSv1.3 in the web server configuration.\n\n"
    "4.2 Ensure server version information is hidden\n"
    "Description: Version banners help attackers pick exploits.\n"
    "Remediation: Set server_tokens to off in the web server configuration."
)

EXAMPLE_REQUIREMENTS = [
    "Disable root login over SSH by setting PermitRootLogin to no",
    "Configure an SSH idle timeout by setting ClientAliveInterval to 300 or less",
    "Enable only TLS 1.2 and TLS 1.3 by setting ssl_protocols to TLSv1.2 TLSv1.3",
    "Hide server version information by setting server_tokens to off",
]

EXAMPLE_OUTPUT_1 = (
    "- element1:\n"
    "    name: \"SSH Daemon Configuration\"\n"
    "    requirements:\n"
    f"      - \"{EXAMPLE_REQUIREMENTS[0]}\"\n"
    f"      - \"{EXAMPLE_REQUIREMENTS[1]}\"\n"
)

EXAMPLE_OUTPUT_2 = (
    "- element1:\n"
    "    name: \"TLS Configuration\"\n"
    "    requirements:\n"
    f"      - \"{EXAMPLE_REQUIREMENTS[2]}\"\n"
    "- element2:\n"
    "    name: \"Information Disclosure\"\n"
    "    requirements:\n"
    f"      - \"{EXAMPLE_REQUIREMENTS[3]}\"\n"
)

# --------------------- #
#    Zero Shot Prompt   #
# --------------------- #

# Takes the string returned by document_reader in extractor.py and puts in in a 
# Zero-Shot prompt for the gemma_3_1b function to process.

def zero_shot(doc_text):

    prompt = (
        f"{task_description}"

        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'

        "Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item). "
        "Output ONLY valid YAML with no preamble, markdown ticks, or commentary:\n"
        f"{output_format}"
    )

    return prompt


# -------------------- #
#    Few Shot Prompt   #
# -------------------- #

# Takes the string returned by document_reader in extractor.py and puts in in a 
# Few-Shot prompt for the gemma_3_1b function to process.
# Provides some specific examples for the LLM to follow.

def few_shot(doc_text):

    prompt = (
        f"{task_description}"

        "--- EXAMPLE 1 ---\n"
        "Document Text:\n"
        f"{EXAMPLE_TEXT_1}\n\n"
        "Output:\n"
        f"{EXAMPLE_OUTPUT_1}"
        "--- END EXAMPLE 1 ---\n\n"

        "--- EXAMPLE 2 ---\n"
        "Document Text:\n"
        f"{EXAMPLE_TEXT_2}\n\n"
        "Output:\n"
        f"{EXAMPLE_OUTPUT_2}"
        "--- END EXAMPLE 2 ---\n\n"

        "Now, process the following document. The examples above are about a different system, so do not reuse their content.\n\n"

        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'

        "Format the output strictly as valid YAML matching this structure from the examples above (incrementing element1, element2, etc. for each item). "
        "Output ONLY valid YAML with no preamble, markdown ticks, or commentary:\n"
        f"{output_format}"
    )

    return prompt


# ----------------------------- #
#     Chain-of-Thought Prompt   #
# ----------------------------- #

# Takes the string returned by document_reader in extractor.py and puts in in a 
# Chain-of-Thought prompt for the gemma_3_1b function to process.
# Prompts the LLM to reason as it goes through the document.

def chain_of_thought(doc_text):

    prompt = (
        f"{task_description}"

        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'

        "Step 1: Before writing the final YAML output, think step by step. For each recommendation, "
        "state which component or configuration area it applies to and what it requires. "
        "Then group the recommendations that apply to the same component.\n\n"

        "Step 2: After your step-by-step breakdown, output the divider \"--- YAML ---\" followed ONLY by the final valid YAML.\n\n"

        "Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item). "
        "After the divider, output strictly valid YAML with no markdown ticks, or commentary:\n"
        f"{output_format}"
    )

    return prompt
