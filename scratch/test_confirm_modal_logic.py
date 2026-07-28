import unittest
import re
from html import unescape

def normalize_confirm_text(text):
    """
    Python equivalent of the JavaScript normalizeConfirmText logic:
    1. Handle None / empty
    2. HTML Entity decoding
    3. Convert non-breaking spaces \u00A0 to ' '
    4. Collapse multiple internal spaces/newlines to a single space
    5. Strip leading and trailing whitespace
    6. Convert to lowercase for user-friendly exact matching
    """
    if text is None:
        return ''
    txt = unescape(str(text))
    s = txt.replace('\u00A0', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

class ConfirmModalMatchingTestCase(unittest.TestCase):

    # Test A — Exact screenshot bug reproduction: "Bachelors Degree"
    def test_exact_screenshot_bug_reproduction(self):
        expected = "Bachelors Degree"
        entered = "Bachelors Degree"
        norm_exp = normalize_confirm_text(expected)
        norm_ent = normalize_confirm_text(entered)
        self.assertEqual(norm_exp, norm_ent)
        self.assertTrue(len(norm_ent) > 0 and norm_exp == norm_ent, "Delete button MUST be enabled")

    # Test B — Leading / trailing / internal / non-breaking whitespace normalization
    def test_whitespace_and_non_breaking_spaces_matches(self):
        expected = "Bachelors Degree"
        entered_spaces = "  Bachelors   Degree  "
        entered_nbsp = "Bachelors\u00A0Degree"
        self.assertEqual(normalize_confirm_text(entered_spaces), normalize_confirm_text(expected))
        self.assertEqual(normalize_confirm_text(entered_nbsp), normalize_confirm_text(expected))

    # Test C — Apostrophes, Quotes, Special Characters, and Unicode
    def test_special_characters_apostrophes_quotes_unicode(self):
        special_cases = [
            ("Bachelor's Degree", "Bachelor's Degree"),
            ("Bachelor's Degree", "bachelor's degree"),
            ("Bachelor's & Master's", "  Bachelor's  &  Master's  "),
            ('Program "Honours"', 'Program "Honours"'),
            ("Computer Science — CS101", "Computer Science — CS101"),
            ("Faculty of O'Reilly & Sons", "Faculty of O'Reilly & Sons"),
            ("Kāmandū University (काठमाडौँ)", "kāmandū university (काठमाडौँ)")
        ]
        for expected, entered in special_cases:
            norm_exp = normalize_confirm_text(expected)
            norm_ent = normalize_confirm_text(entered)
            self.assertEqual(norm_exp, norm_ent, f"Special character match failed for '{expected}'")

    # Test D — Partial text rejection
    def test_partial_text_rejected(self):
        expected = "Bachelors Degree"
        self.assertNotEqual(normalize_confirm_text("Bachelor"), normalize_confirm_text(expected))
        self.assertNotEqual(normalize_confirm_text("Bachelors"), normalize_confirm_text(expected))
        self.assertNotEqual(normalize_confirm_text("Degree"), normalize_confirm_text(expected))

    # Test E — Mismatched text rejection
    def test_wrong_text_rejected(self):
        expected = "Bachelors Degree"
        entered_wrong = "Bachelors Degree 123"
        self.assertNotEqual(normalize_confirm_text(entered_wrong), normalize_confirm_text(expected))

    # Test F — All 7 permanent deletion target scenarios
    def test_all_seven_deletion_targets(self):
        targets = [
            ("Education Level", "Bachelors Degree", "bachelors degree"),
            ("University", "Asia Pacific University (APU)", "Asia Pacific University (APU)"),
            ("Faculty", "Science & Technology", "science & technology"),
            ("Academic Program", "BSc IT (Cloud Computing)", "bsc it (cloud computing)"),
            ("Master Subject", "Mathematics MATH101", "mathematics math101"),
            ("Student Email", "student@example.com", "STUDENT@EXAMPLE.COM"),
            ("Regular Admin Email", "admin@example.com", "  admin@example.com  ")
        ]
        for entity, expected, entered in targets:
            norm_exp = normalize_confirm_text(expected)
            norm_ent = normalize_confirm_text(entered)
            self.assertEqual(norm_exp, norm_ent, f"Matching failed for {entity}")

if __name__ == '__main__':
    unittest.main()
