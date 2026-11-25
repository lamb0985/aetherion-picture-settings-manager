import unittest
from schema import SOURCE_NAMES, source_name

class SourceNamesTests(unittest.TestCase):
    def test_known_input_ids(self):
        self.assertEqual(SOURCE_NAMES, {4:"HDMI 1",5:"HDMI 2",6:"HDMI 3",9:"Google TV"})
        for source, name in SOURCE_NAMES.items():
            self.assertEqual(source_name(source), name)
    def test_unknown_and_missing(self):
        self.assertEqual(source_name(42), "Source 42")
        self.assertEqual(source_name(0), "Source 0")
        self.assertIsNone(source_name(None))
