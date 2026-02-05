import unittest


class TestDrupalOrgUrls(unittest.TestCase):
    def test_build_project_issue_search_url_no_keywords(self):
        from lib.drupalorg_urls import build_project_issue_search_url

        self.assertEqual(
            build_project_issue_search_url("webform", []),
            "https://www.drupal.org/project/issues/search/webform",
        )

    def test_build_project_issue_search_url_encodes_keywords(self):
        from lib.drupalorg_urls import build_project_issue_search_url

        self.assertEqual(
            build_project_issue_search_url("webform", ["timezone datetime", "reference"]),
            "https://www.drupal.org/project/issues/search/webform?text=timezone+datetime+reference",
        )


if __name__ == "__main__":
    unittest.main()

