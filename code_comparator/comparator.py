''' 
Courtney Lin, Nicholas Marden
Task 2 - Comparator
'''

# -------------------------------------- #
#          - Comparator File -           #
#     Document Processing Functions      #
# -------------------------------------- #

import yaml
import os

# ---------------------------- #
#     YAML Document Reader     #
# ---------------------------- #

# load_yaml_input(): Takes YAML generated in extractor and puts elements into a dict.
# load_files(): Calls load_yaml_input() twice; once for each of the two YAMLs being compared.

def load_yaml_input(doc_path):

    # Same error checking from document_reader() in extractor.py.

    if not isinstance(doc_path, str) or not doc_path.strip():
        raise TypeError("Input must be a non-empty file path string.")
    if not os.path.isfile(doc_path):
        raise FileNotFoundError(f"File not found: {doc_path}")
    if not doc_path.lower().endswith(".yaml"):
        raise ValueError(f"Invalid File Extension: '{doc_path}'. Input must be a YAML file.")

    with open(doc_path) as f:
        data = yaml.safe_load(f)

    # Error check if file is empty or not a mapping of YAML elements.
    if not isinstance(data, dict):
        raise ValueError(f"'{doc_path}' is empty or not a YAML mapping of elements.")

    # Loading a YAML file and putting contents into a dictionary in this format:
        # Key: element name
        # Value: [list of requirements for that element]

    content = {}

    for key, element in data.items():
        # If for some reason the dict value isn't another dict (name: [reqs])
        # Or if the element has no name for some reason.
        if not isinstance(element, dict) or not element.get("name"):
            raise ValueError(f"Element '{key}' in '{doc_path}' has no valid 'name'.")
        name = element["name"].strip()
        content.setdefault(name, []).extend(element.get("requirements") or [])

    return content


def load_files(path1, path2):
    return load_yaml_input(path1), load_yaml_input(path2)


# --------------------------------------------- #
#     Differences with Respect to KDE Names     #
# --------------------------------------------- #

def id_differences_in_names(doc1, doc2):

    # Finds the set differences between doc1 and doc2 and takes the element names that are only 
    # present in one of the files. If the resulting objects of names are both empty, then there are
    # no discernable differences between each of the files.

    output_path = "difference_names.txt"

    only_doc1_names = doc1.keys() - doc2.keys()
    only_doc2_names = doc2.keys() - doc1.keys()

    with open(output_path, "w") as f:
        if not only_doc1_names and not only_doc2_names:
            f.write("NO DIFFERENCE IN REGARDS TO ELEMENT NAMES\n")
        else:
            f.write("Names only in file 1:\n")
            for name in sorted(only_doc1_names):
                f.write(f"{name}\n")

            f.write("\nNames only in file 2:\n")
            for name in sorted(only_doc2_names):
                f.write(f"{name}\n")


# --------------------------------------------------------- #
#     Differences with Respect to Key Data Requirements     #
# --------------------------------------------------------- #

# find_unique_reqs(): Finds requirements that are unique to only the first document
# id_differences_in_requirements(): Compares the remaining requirements and write them to .txt file.

def find_unique_reqs(doc1, doc2):

    missing = []

    for name, reqs in doc1.items():
        other = set(doc2.get(name, []))   # Empty if the name isn't in doc2
        for req in reqs:
            if req not in other:
                missing.append((name, req))

    return missing


def id_differences_in_requirements(doc1, doc2):

    # Similar to id_differences_in_names(), find the requirements that are only present
    # in one of the files. If the resulting objects of names are both empty, then there are
    # no discernable differences between each of the files.

    output_path = "difference_requirements.txt"

    only_doc1 = find_unique_reqs(doc1, doc2)
    only_doc2 = find_unique_reqs(doc2, doc1)

    with open(output_path, "w") as f:
        if not only_doc1 and not only_doc2:
            f.write("NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS\n")
        else:
            f.write("Requirements only in file 1:\n")
            for name, req in sorted(only_doc1):
                f.write(f"{name},{req}\n")
            
            f.write(f"\nRequirements only in file 2:\n")
            for name, req in sorted(only_doc2):
                f.write(f"{name},{req}\n")
