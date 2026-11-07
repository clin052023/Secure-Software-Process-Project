''' 
Courtney Lin, Nicholas Marden
Task 2 - Comparator
'''

# -------------------------------------------- #
#          - Comparator Test Cases -           #
# -------------------------------------------- #

# One test case for 3 functions in comparator.py.
# Run in terminal (from the project root):
#     python3 -m unittest task2_comparator.test_comparator -v
#     python3 -m unittest discover -v

import os
import unittest
import tempfile

try:                                    # `python3 -m unittest ...` (package import)
    from .comparator import (load_yaml_input, id_differences_in_names,
                             id_differences_in_requirements)
except ImportError:                     # plain script run from inside the folder
    from comparator import (load_yaml_input, id_differences_in_names,
                            id_differences_in_requirements)


class TestComparatorFunctions(unittest.TestCase):

    # Run in a temporary directory so the hardcoded output filenames don't overwrite real output files.

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()


    # ------------------------------------------ #
    #          - Function Test Cases -           #
    # ------------------------------------------ #

    def test_load_yaml(self):

        yaml_text = (
            "element1:\n"
            "  name: Docker Auditing\n"
            "  requirements:\n"
            "  - rule A\n"
            "  - rule B\n"
        )

        with open("sample.yaml", "w") as f:
            f.write(yaml_text)

        # Output must match structure:
            # Key: element name
            # Value: [list of requirements for that element]

        self.assertEqual(load_yaml_input("sample.yaml"), {"Docker Auditing": ["rule A", "rule B"]})


    def test_name_difference(self):

        doc1 = {"A": ["r1"], "B": ["r2"]}
        doc2 = {"B": ["r2"], "C": ["r3"]}

        id_differences_in_names(doc1, doc2)
        with open("difference_names.txt") as f:
            out = f.read()

        # Output must only contain the element names that are NOT present in both files.

        self.assertIn("A", out)
        self.assertIn("C", out)
        self.assertNotIn("B", out)


    def test_requirment_difference(self):

        doc1 = {"A": ["r1", "r2"]}
        doc2 = {"A": ["r1", "r3"]}

        id_differences_in_requirements(doc1, doc2)
        with open("difference_requirements.txt") as f:
            out = f.read()

        # Output must only contain requirements that are NOT present in both files,
        # regardless of element name.

        self.assertIn("A,r2", out)
        self.assertIn("A,r3", out)
        self.assertNotIn("A,r1", out)


if __name__ == "__main__":
    unittest.main()
