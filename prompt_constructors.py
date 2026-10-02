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

# Format for Gemma-3-1b to follow for the desired output
output_format = """
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
"""

# --------------------- #
#    Zero Shot Prompt   #
# --------------------- #

# Takes the string returned by document_reader in extractor.py and puts in in a 
# Zero-Shot prompt for the gemma_3_1b function to process.

def zero_shot(doc_text):

    prompt = (
        "Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.\n\n"
        
        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'
        
        "Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item)."
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
        "Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.\n\n"
        
        "--- EXAMPLE 1 ---\n"
        "Document Text:\n"
        "\"3.1 Access Control: All administrative accounts must enforce Multi-Factor Authentication (MFA). Passwords must be at least 16 characters long and changed every 90 days.\"\n\n"

        "Output:\n"
        "- element1:\n"
        "    name: \"Access Control\"\n"
        "    requirements:\n"
        "    - \"All administrative accounts must enforce Multi-Factor Authentication (MFA)\"\n"
        "    - \"Passwords must be at least 16 characters long\"\n"
        "    - \"Passwords must be changed every 90 days\"\n"
        "--- END EXAMPLE 1 ---\n\n"

        "--- EXAMPLE 2 ---\n"
        "Document Text:\n"
        "\"Section 5 - Data Encryption: Sensitive data at rest must use AES-256 encryption. Data in transit must be encrypted using TLS 1.3.\"\n\n"

        "Output:\n"
        "- element1:\n"
        "    name: \"Data Encryption\"\n"
        "    requirements:\n"
        "    - \"Sensitive data at rest must use AES-256 encryption\"\n"
        "    - \"Data in transit must be encrypted using TLS 1.3\"\n"
        "--- END EXAMPLE 2 ---\n\n"
        
        "Now, process the following document.\n\n"

        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'

        "Format the output strictly as valid YAML matching this structure from the examples above (incrementing element1, element2, etc. for each item)."
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
        "Read the following document text and identify Key Data Elements (KDEs) for the file's specified security requirements.\n\n"

        "Document:\n"
        '\"\"\"\n'
        f"{doc_text}\n"
        '\"\"\"\n\n'

        "Step 1: Before writing the final YAML output, output your reasoning as you think through the document. List each major security section you find and summarize its key rules.\n\n"
        
        "Step 2: After your step-by-step breakdown, output the divider \"--- YAML ---\" followed ONLY by the final valid YAML.\n\n"
        
        "Format the output strictly as valid YAML matching this structure (incrementing element1, element2, etc. for each item)."
        "After the divider, output strictly valid YAML with no markdown ticks, or commentary:\n"
        f"{output_format}"
    )

    
    return prompt
