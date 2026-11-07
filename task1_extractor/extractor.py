''' 
Courtney Lin, Nicholas Marden
Task 1 - Extractor
'''

# ------------------------------------- #
#          - Extractor File -           #
#     Document Processing Functions     #
#       + (prompt_constructors.py)      #
# ------------------------------------- #

# import prompt_constructors.py files and other libraries here if needed
try:
    from .prompt_constructors import (zero_shot, few_shot, chain_of_thought,
                                     EXAMPLE_REQUIREMENTS, EXAMPLE_TEXT_1, EXAMPLE_TEXT_2)
except ImportError:                     # run as a loose module from inside this folder
    from prompt_constructors import (zero_shot, few_shot, chain_of_thought,
                                    EXAMPLE_REQUIREMENTS, EXAMPLE_TEXT_1, EXAMPLE_TEXT_2)
# run in terminal: pip install pypdf pyyaml torch transformers accelerate
from pypdf import PdfReader
from pypdf.errors import PdfReadError
# to check if path exists
import os
# for cleaning up Gemma's output before parsing it as YAML
import re
# for parsing the LLM output into a nested dictionary and dumping it to YAML files
import yaml


# --------------------------- #
#     PDF Document Reader     #
# --------------------------- #

# Takes a document as input and applies adequate input validation methods.
# Probably means to make sure the files are valid types like PDFs.
# The plan is to call this function twice; once for each of the two documents that we're comparing.

def document_reader(doc_path):

    # Input validation: the path must be a non-empty string.
    if not isinstance(doc_path, str) or not doc_path.strip():
        raise TypeError("Input must be a non-empty file path string.")

    # Checking to see if the file exists first; if it doesn't, then it an error is raised.
    if not os.path.isfile(doc_path):
        raise FileNotFoundError(f"File not found: {doc_path}")

    # Input validation: make sure the file has a .pdf extension.
    if not doc_path.lower().endswith(".pdf"):
        raise ValueError(f"Invalid File Extension: '{doc_path}'. Input must be a PDF file.")

    # Checking the PDF file header signature to make sure it is a PDF file.
    # The first 5 bytes should resemble '%PDF-'.
    with open(doc_path, 'rb') as f:
        file_header = f.read(5)
    if file_header != b'%PDF-':
        raise ValueError(f"Invalid File Type: '{doc_path}'. Input must be a PDF file.")

    # Input validation: try to open the file with PdfReader; a corrupt PDF raises here too.
    try:
        reader = PdfReader(doc_path)
    except PdfReadError as e:
        raise ValueError(f"Corrupt or unreadable PDF: '{doc_path}'. ({e})") from e

    # Input validation: a PDF with no readable pages has nothing for the LLM to work with.
    if not reader.pages:
        raise ValueError(f"Empty PDF: '{doc_path}'. No readable pages found.")

    # Now we read the file and turn the PDF text into a regular continuous Python string
    text = ""
    for page in reader.pages:
        try:
            extracted = page.extract_text()
        except Exception as e:
            raise ValueError(f"Unreadable page in '{doc_path}'. ({e})") from e
        if extracted:
            text += extracted.strip() + "\n"

    # Input validation: make sure we actually extracted some text out of the PDF.
    if not text.strip():
        raise ValueError(f"No extractable text: '{doc_path}'. The PDF may be scanned images only.")

    # Clean up any leading/trailing spaces/tabs/newlines from the string and return it.
    return text.strip()


# ------------------------------------------ #
#     Benchmark Text Pre-processing          #
# ------------------------------------------ #

# The raw PDF text is mostly noise for this task: table of contents, page headers, rationale,
# audit commands, references and the appendix tables (which is where the junk "77", "78" style
# requirements came from). Each CIS recommendation is reduced to its number, title, Description
# and Remediation. That is about 6x less text, so there are far fewer LLM calls, and the model
# only sees text that actually states requirements.
# If a document has no CIS-style recommendations (e.g. the small test PDFs) it is left unchanged.

_NOISE = re.compile(r"Internal Only - General|Page \d+(?=\s|$)")
_REC = re.compile(
    r"(?:(?<=\s)|^)(\d+(?:\.\d+)+)\s+"
    r"((?:(?!\s\d+\.\d+(?:\.\d+)*\s)(?!\((?:Manual|Automated)\)).){5,300}?)"
    r"\s*\((?:Manual|Automated)\)\s+Profile Applicability:")

def _truncate(text, max_len):
    # Cuts text to at most max_len characters at a sentence end if possible (otherwise at a
    # word boundary), so requirements are never cut off in the middle of a word.
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    end = max(cut.rfind(". "), cut.rfind(".\n"))
    if end >= max_len * 0.4:
        return cut[:end + 1]
    return cut[:cut.rfind(" ")] if " " in cut else cut


def _field(body, label, stops):
    m = re.search(re.escape(label) + r"\s*(.*)", body)
    if not m:
        return ""
    rest = m.group(1)
    cut = len(rest)
    for s in stops:
        i = rest.find(s)
        if i != -1:
            cut = min(cut, i)
    return rest[:cut].strip()

def condense_cis_text(text, max_field=600):
    # Returns the condensed text, or the original text if no recommendations are found.
    flat = re.sub(r"\s+", " ", _NOISE.sub(" ", text))
    matches = list(_REC.finditer(flat))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(flat)
        body = flat[m.end():end]
        desc = _field(body, "Description:", [" Rationale:", " Impact:", " Audit:", " Remediation:"])
        rem = _field(body, "Remediation:", [" Default Value:", " References:", " CIS Controls:", " Appendix:"])
        parts = [f"{m.group(1)} {m.group(2).strip()}"]
        if desc: parts.append("Description: " + _truncate(desc, max_field))
        if rem:  parts.append("Remediation: " + _truncate(rem, max_field))
        out.append("\n".join(parts))
    return "\n\n".join(out) if out else text


# --------------------------- #
#     Gemma-3-1B Function     #
# --------------------------- #

# Uses the prompts generated by prompt constructor functions and 
# evaluates the inputted documents with Gemma-3-1B LLM.
# Saves the generated output in a YAML file.

# This function also generates a nested dictionary in this format:
"""
- element1:
    name:
    requirements:
      - req1
      - req2
      - req3
        ...
"""

# And this is saved into a YAML file, which is named after the input document.
# (ex. cis-r1-kdes.yaml)

# LLM setup: Gemma-3-1B is run locally through Hugging Face (transformers).
#
# One-time setup:
#   1) install the libraries:   pip install torch transformers accelerate
#   2) Gemma is a GATED model. Accept the license once at:
#      https://huggingface.co/google/gemma-3-1b-it
#   3) use your Hugging Face READ token, either with `huggingface-cli login`
#      (stored on disk) or by setting the environment variable HF_TOKEN before
#      running this script (see the HF_TOKEN line below).
#   4) the weights (~2 GB) download automatically on the first call and are
#      then cached in ~/.cache/huggingface, so later runs start instantly.
HF_MODEL_ID = "google/gemma-3-1b-it"
LLM_NAME = "Gemma-3-1B"

# Your Hugging Face read token. If the environment variable HF_TOKEN is set it is
# used automatically; otherwise paste the token between the quotes. It only needs
# to be set if you have not run `huggingface-cli login`. Never commit a real token.
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# How many tokens the model may generate for one requirement-extraction answer.
MAX_NEW_TOKENS = 1024

# A 1B model only handles a handful of recommendations per call: with ~25 in one prompt it summarised
# a few and skipped the rest. Documents are therefore split into small chunks (about 8 recommendations,
# ~1k tokens) and each chunk is sent to the model separately. Small chunks also keep the attention mask
# tiny, which is what avoids the CUDA out-of-memory error the full PDF text caused.
CHUNK_CHARS = 4000

# Every LLM call made through gemma_3_1b is logged here so that
# output_txt_collector() can dump them all to a TEXT file later.
LLM_LOG = []

# The transformers pipeline is loaded once and reused for every call; loading it
# per call would re-read the 2 GB of weights each time. It stays None until the
# first call, so importing this module is cheap and needs no torch installed.
_HF_PIPELINE = None

# Where the model ended up running ("cuda" or "cpu"); set on the first load.
LLM_DEVICE = None

# Reduces CUDA memory fragmentation. Must be set before torch initialises CUDA,
# which is why it happens here, at import time (torch is imported lazily below).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def _build_pipeline(device_map):
    # Builds the Gemma-3-1B text-generation pipeline on the requested device.
    # dtype="auto" loads the weights in the checkpoint's own 16-bit format
    # instead of upcasting to float32, which halves GPU memory use.
    from transformers import pipeline
    # Silences the repeated "max_new_tokens / max_length" and other harmless warnings.
    # Done here (not at the top of the file) so importing this module stays cheap.
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()

    return pipeline(
        "text-generation",
        model=HF_MODEL_ID,
        token=HF_TOKEN or None,   # None -> falls back to the token saved by `huggingface-cli login`
        dtype="auto",
        device_map=device_map,
    )


def _get_hf_pipeline():
    # Loads (once) the Gemma-3-1B text-generation pipeline from Hugging Face.
    # Tries the GPU first and falls back to the CPU if the GPU is out of memory.
    global _HF_PIPELINE, LLM_DEVICE
    if _HF_PIPELINE is not None:
        return _HF_PIPELINE

    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "Hugging Face backend needs torch and transformers. "
            "Run: pip install torch transformers accelerate"
        ) from e

    try:
        _HF_PIPELINE = _build_pipeline("auto")   # GPU if one has room, CPU otherwise
    except torch.cuda.OutOfMemoryError:
        print("GPU out of memory; running Gemma-3-1B on the CPU instead "
              "(slower, but it will finish).")
        torch.cuda.empty_cache()
        _HF_PIPELINE = _build_pipeline("cpu")
    except RuntimeError as e:
        # Older torch uses RuntimeError for OOM instead of torch.cuda.OutOfMemoryError.
        if "out of memory" not in str(e).lower():
            raise
        print("GPU out of memory; running Gemma-3-1B on the CPU instead "
              "(slower, but it will finish).")
        torch.cuda.empty_cache()
        _HF_PIPELINE = _build_pipeline("cpu")

    LLM_DEVICE = str(getattr(_HF_PIPELINE, "device", "unknown"))
    return _HF_PIPELINE


def _call_gemma(prompt, max_new_tokens=MAX_NEW_TOKENS):
    # Sends one prompt to Gemma-3-1B through Hugging Face transformers and
    # returns the text the model generated (not the prompt it was given).
    pipe = _get_hf_pipeline()

    # Gemma-3 is an instruction-tuned chat model, so the prompt goes in as a
    # chat message and the pipeline applies the model's chat template.
    messages = [{"role": "user", "content": prompt}]
    result = pipe(messages, max_new_tokens=max_new_tokens, do_sample=False)

    generated = result[0]["generated_text"]
    if isinstance(generated, list):
        # Chat input -> the whole conversation comes back; the answer is the last turn.
        return generated[-1]["content"]
    return str(generated)


def _clean_yaml_output(raw):
    # Cleans up the LLM's raw output so it can be parsed as YAML.
    # Chain-of-thought output gets its reasoning stripped first; the final YAML
    # comes after the divider the CoT prompt asks for.
    if "--- YAML ---" in raw:
        raw = raw.split("--- YAML ---", 1)[1]

    # Strip markdown code fences if Gemma added them anyway.
    fence = re.search(r"```(?:ya?ml)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)

    return raw.strip()


def _parse_llm_output(raw):
    # Turns the cleaned raw output into a Python object (list or dict), or None if it can't be parsed.
    cleaned = _clean_yaml_output(raw)
    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError:
        return None
    if not isinstance(data, (list, dict)):
        return None
    return data


_PLACEHOLDER_RE = re.compile(r"^(req\d*|element\s*name|element\d*)$", re.IGNORECASE)


def _words(text):
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


# Everything the few-shot prompt shows the model (its answers and the example text itself),
# kept as word sets. A requirement that is mostly made of these words was copied from the
# examples, not read from the document (the model rephrases them slightly, so exact matching fails).
_EXAMPLE_SOURCES = [_words(r) for r in EXAMPLE_REQUIREMENTS]
for _example in (EXAMPLE_TEXT_1, EXAMPLE_TEXT_2):
    for _line in re.split(r"\n|(?<=\.)\s", _example):
        if len(_line.split()) >= 4:
            _EXAMPLE_SOURCES.append(_words(re.sub(r"^\d+\.\d+\s+|^(Description|Remediation):\s*", "", _line)))


def _copies_example(req):
    w = _words(req)
    if len(w) < 4:
        return False
    return any(len(w & src) / len(w) >= 0.7 and len(w & src) >= 4 for src in _EXAMPLE_SOURCES)



def _is_junk_requirement(req):
    # True for things the 1B model produces that are not real requirements:
    # skeleton placeholders ("req1", "<...>"), bare numbers (page/section numbers), fragments
    # shorter than 3 words, and the few-shot example sentences copied back out.
    r = req.strip().strip('"\'').strip()
    if not r or _PLACEHOLDER_RE.match(r):
        return True
    if "<" in r and ">" in r:
        return True
    if not re.search(r"[A-Za-z]", r):
        return True
    if len(r.split()) < 3:
        return True
    return _copies_example(r)


# Section labels of the benchmark itself, not components a requirement applies to.
_BOILERPLATE_NAMES = {"profile applicability", "cis controls", "table of contents", "terms of use"}


def _is_junk_name(name):
    n = name.strip().strip('"\'').strip()
    return ((not n) or bool(_PLACEHOLDER_RE.match(n)) or ("<" in n and ">" in n)
            or n.lower() in _BOILERPLATE_NAMES)


def _req_to_text(req):
    # YAML turns "Run the daemon as below: dockerd --x" into a one-key dict, and the model
    # sometimes returns nested lists. Both are turned back into one plain sentence.
    if isinstance(req, dict):
        return "; ".join(f"{_req_to_text(k)}: {_req_to_text(v)}" for k, v in req.items())
    if isinstance(req, (list, tuple)):
        return " ".join(_req_to_text(r) for r in req)
    return str(req).strip()


def _extract_elements(data):
    # Flattens any parsed output into a simple list of {"name": ..., "requirements": [...]}.
    # Junk requirements are removed, and elements left with no real requirement (or with a
    # placeholder name) are dropped.
    elements = []
    if isinstance(data, dict):
        items = list(data.items())
    elif isinstance(data, list):
        # A list of single-key dicts: [{"element1": {...}}, {"element2": {...}}]
        items = [(k, v) for d in data if isinstance(d, dict) for k, v in d.items()]
    else:
        return elements

    for key, value in items:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name", key)).strip() or str(key)
        if _is_junk_name(name):
            continue
        reqs = value.get("requirements", [])
        if isinstance(reqs, (str, dict)):
            reqs = [reqs]
        reqs = [_req_to_text(r) for r in (reqs or [])]
        reqs = [r for r in reqs if r]
        reqs = [r for r in reqs if not _is_junk_requirement(r)]
        if not reqs:
            continue
        elements.append({"name": name, "requirements": reqs})
    return elements


def _name_key(name):
    # Normalised KDE name used to merge near-duplicates:
    # "Docker Daemon", "docker daemons" and "Daemon" all map to the same key.
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    words = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w != "docker"]
    return " ".join(words) or name.lower()


def _req_key(req):
    # Normalised requirement text used for de-duplication (case, spacing, trailing period).
    return re.sub(r"\s+", " ", req.lower()).strip().rstrip(".")


def _merge_elements(parsed_outputs):
    # Merges the KDEs from every prompt and chunk into one nested dictionary.
    # One KDE can map to multiple requirements: KDEs whose names normalise to the same key
    # (see _name_key) are combined, and their requirement lists are merged without duplicates.
    merged = []
    for elements in parsed_outputs:
        for element in elements:
            key = _name_key(element["name"])
            for existing in merged:
                if existing["key"] == key:
                    seen = {_req_key(r) for r in existing["requirements"]}
                    for req in element["requirements"]:
                        if _req_key(req) not in seen:
                            existing["requirements"].append(req)
                            seen.add(_req_key(req))
                    break
            else:
                reqs, seen = [], set()
                for req in element["requirements"]:
                    if _req_key(req) not in seen:
                        reqs.append(req)
                        seen.add(_req_key(req))
                merged.append({"key": key, "name": element["name"], "requirements": reqs})

    # A requirement can appear under several differently named KDEs ("Host Device Exposure",
    # "Device Permissions", ...). It is kept under the first one only; KDEs left empty are dropped.
    seen_global = set()
    nested = {}
    i = 0
    for element in merged:
        reqs = []
        for req in element["requirements"]:
            if _req_key(req) not in seen_global:
                seen_global.add(_req_key(req))
                reqs.append(req)
        if not reqs:
            continue
        i += 1
        nested[f"element{i}"] = {"name": element["name"], "requirements": reqs}
    return nested


def _chunk_text(text, max_chars=CHUNK_CHARS):
    # Splits text into chunks of at most max_chars characters, breaking on line boundaries.
    # When a chunk fills up it is cut at its last blank line if it has one, so a
    # recommendation (blocks are separated by blank lines) is not split in the middle.
    chunks, current, size = [], [], 0
    for line in text.splitlines():
        # A single enormous line is hard-split so no chunk can exceed max_chars.
        while len(line) > max_chars:
            if current:
                chunks.append("\n".join(current))
                current, size = [], 0
            chunks.append(line[:max_chars])
            line = line[max_chars:]
        while current and size + len(line) + 1 > max_chars:
            cut = max((i for i, l in enumerate(current) if not l.strip()), default=0)
            if cut > 0:
                chunks.append("\n".join(current[:cut]))
                current = current[cut + 1:]
            else:
                chunks.append("\n".join(current))
                current = []
            size = sum(len(l) + 1 for l in current)
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _run_prompt(prompt_text, prompt_type, doc_name, llm_fn=None):
    # Runs one prompt through the LLM, logs the call, and parses the output.
    # llm_fn lets a test inject a fake LLM; production calls go through _call_gemma().
    raw = llm_fn(prompt_text) if llm_fn is not None else _call_gemma(prompt_text)

    LLM_LOG.append({
        "llm": LLM_NAME,
        "prompt": prompt_text,
        "type": prompt_type,
        "output": raw,
        "doc": doc_name,
    })

    return _parse_llm_output(raw)


def gemma_3_1b(doc1_str, doc2_str, doc3_str=None,
               doc1_name="docker-cis-v0.pdf",
               doc2_name="docker-cis-v1.pdf",
               doc3_name="docker-cis-v2.pdf",
               yaml_dir=".", llm_fn=None):

    # Splits each document into chunks, runs each of the three constructed prompts on every chunk, then merges
    # the results into one nested KDE dictionary per document and saves it as YAML.
    # There are three input documents (v0, v1, v2); doc3_str can be set to None to
    # run with only two. The YAML file names are built from the input document names:
    #   'docker-cis-v0.pdf' -> 'docker-cis-v0-kdes.yaml'
    docs = [(doc1_name, doc1_str), (doc2_name, doc2_str)]
    if doc3_str is not None:
        docs.append((doc3_name, doc3_str))

    results = {}

    prompt_fns = [
        (zero_shot,        "zero-shot"),
        (few_shot,         "few-shot"),
        (chain_of_thought, "chain-of-thought"),
    ]

    for doc_name, doc_text in docs:
        # Each chunk goes through all three prompt types; outputs that can't be parsed are dropped.
        parsed_outputs = []
        # Reduce the PDF text to the recommendations themselves, then split it into chunks.
        chunks = _chunk_text(condense_cis_text(doc_text))
        for n, chunk in enumerate(chunks, start=1):
            print(f"{doc_name}: chunk {n}/{len(chunks)}", flush=True)
            for prompt_fn, prompt_type in prompt_fns:
                parsed = _run_prompt(prompt_fn(chunk), prompt_type, doc_name, llm_fn)
                if parsed is not None:
                    parsed_outputs.append(parsed)

        # Merge everything that was parsed (across chunks and prompt types).
        nested = _merge_elements([_extract_elements(d) for d in parsed_outputs])

        stem = os.path.splitext(os.path.basename(str(doc_name)))[0]
        yaml_path = os.path.join(yaml_dir, f"{stem}-kdes.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(nested, f, sort_keys=False, allow_unicode=True)

        results[os.path.basename(str(doc_name))] = nested

    return results


# ---------------------------------- #
#        LLM Output Collector        #
# ---------------------------------- #

# Automatically collects all LLM output and saves it to a TEXT file in this format:
"""
    *LLM Name*
    ...
    *Prompt Used*
    ...
    *Prompt Type (zero-shot, few-shot, chain-of-thought)*
    ...
    *LLM Output*
"""

def output_txt_collector(txt_path="llm-outputs.txt", log=LLM_LOG):

    if not log:
        raise ValueError("No LLM calls have been recorded yet. Run gemma_3_1b() first.")

    blocks = []
    for entry in log:
        blocks.append(
            "*LLM Name*\n"
            f"{entry['llm']}\n"
            "*Prompt Used*\n"
            f"{entry['prompt']}\n"
            "*Prompt Type (zero-shot, few-shot, chain-of-thought)*\n"
            f"{entry['type']}\n"
            "*LLM Output*\n"
            f"{entry['output'].strip() if entry['output'].strip() else '(no output)'}\n"
        )

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))

    return txt_path
