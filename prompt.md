# PROMPT.md
*Courtney Lin, Nicholas Marden*

**All prompts used during Task 1 (Extractor).**

Before prompting, `extractor.py` reduces each benchmark PDF to its numbered recommendations
(number, title, Description and Remediation) with `condense_cis_text()`, and splits the result into
chunks of at most 4,000 characters (about 8 recommendations). Each prompt below is run once per chunk, and the `{doc_text}`
placeholder is replaced with that chunk. The YAML skeleton shown as `{output_format}` in the prompts is:

```yaml
- element1:
    name: "<name of a security component or configuration area>"
    requirements:
      - "<one complete requirement sentence>"
      - "<another complete requirement sentence>"
- element2:
    name: "<name of a different component or area>"
    requirements:
      - "<one complete requirement sentence>"
```

## zero-shot

**Zero-Shot 1 — KDE extraction (`zero_shot()` in prompt_constructors.py):**

```text
The text below contains numbered security recommendations from a security benchmark. Each one has a Description and a Remediation.
Identify the Key Data Elements (KDEs): the components or configuration areas that the recommendations apply to (for example a daemon, a configuration file, a network, or an image). For each KDE, list the security requirements that apply to it as short, complete sentences based on the recommendations. Use only information from the document, and do not copy the examples. If the text contains no security requirements, output exactly: []

Document:
"""
{doc_text}
"""

Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item). Output ONLY valid YAML with no preamble, markdown ticks, or commentary:

- element1:
    name: "<name of a security component or configuration area>"
    requirements:
      - "<one complete requirement sentence>"
      - "<another complete requirement sentence>"
- element2:
    name: "<name of a different component or area>"
    requirements:
      - "<one complete requirement sentence>"
```

## few-shot

**Few-Shot 1 — two worked examples (`few_shot()` in prompt_constructors.py):**

```text
The text below contains numbered security recommendations from a security benchmark. Each one has a Description and a Remediation.
Identify the Key Data Elements (KDEs): the components or configuration areas that the recommendations apply to (for example a daemon, a configuration file, a network, or an image). For each KDE, list the security requirements that apply to it as short, complete sentences based on the recommendations. Use only information from the document, and do not copy the examples. If the text contains no security requirements, output exactly: []

--- EXAMPLE 1 ---
Document Text:
2.1 Ensure SSH root login is disabled
Description: Logging in directly as root removes accountability for administrative actions.
Remediation: Set PermitRootLogin to no in /etc/ssh/sshd_config and restart the SSH service.

2.2 Ensure SSH idle timeout is configured
Description: Idle sessions left open can be hijacked.
Remediation: Set ClientAliveInterval to 300 or less in /etc/ssh/sshd_config.

Output:
- element1:
    name: "SSH Daemon Configuration"
    requirements:
      - "Disable root login over SSH by setting PermitRootLogin to no"
      - "Configure an SSH idle timeout by setting ClientAliveInterval to 300 or less"
--- END EXAMPLE 1 ---

--- EXAMPLE 2 ---
Document Text:
4.1 Ensure only modern TLS versions are enabled
Description: Older TLS versions have known weaknesses.
Remediation: Set ssl_protocols to TLSv1.2 TLSv1.3 in the web server configuration.

4.2 Ensure server version information is hidden
Description: Version banners help attackers pick exploits.
Remediation: Set server_tokens to off in the web server configuration.

Output:
- element1:
    name: "TLS Configuration"
    requirements:
      - "Enable only TLS 1.2 and TLS 1.3 by setting ssl_protocols to TLSv1.2 TLSv1.3"
- element2:
    name: "Information Disclosure"
    requirements:
      - "Hide server version information by setting server_tokens to off"
--- END EXAMPLE 2 ---

Now, process the following document. The examples above are about a different system, so do not reuse their content.

Document:
"""
{doc_text}
"""

Format the output strictly as valid YAML matching this structure from the examples above (incrementing element1, element2, etc. for each item). Output ONLY valid YAML with no preamble, markdown ticks, or commentary:

- element1:
    name: "<name of a security component or configuration area>"
    requirements:
      - "<one complete requirement sentence>"
      - "<another complete requirement sentence>"
- element2:
    name: "<name of a different component or area>"
    requirements:
      - "<one complete requirement sentence>"
```

## chain-of-thought

**Chain-of-Thought 1 — reasoning before the YAML (`chain_of_thought()` in prompt_constructors.py):**

```text
The text below contains numbered security recommendations from a security benchmark. Each one has a Description and a Remediation.
Identify the Key Data Elements (KDEs): the components or configuration areas that the recommendations apply to (for example a daemon, a configuration file, a network, or an image). For each KDE, list the security requirements that apply to it as short, complete sentences based on the recommendations. Use only information from the document, and do not copy the examples. If the text contains no security requirements, output exactly: []

Document:
"""
{doc_text}
"""

Step 1: Before writing the final YAML output, think step by step. For each recommendation, state which component or configuration area it applies to and what it requires. Then group the recommendations that apply to the same component.

Step 2: After your step-by-step breakdown, output the divider "--- YAML ---" followed ONLY by the final valid YAML.

Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item). After the divider, output strictly valid YAML with no markdown ticks, or commentary:

- element1:
    name: "<name of a security component or configuration area>"
    requirements:
      - "<one complete requirement sentence>"
      - "<another complete requirement sentence>"
- element2:
    name: "<name of a different component or area>"
    requirements:
      - "<one complete requirement sentence>"
```
