import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts import run_pipeline as pipeline
from scripts.fetch_paper_ids import parse_listing


PAPER = {
    "id": "2611.12345",
    "title": "A sample paper",
    "abstract": "An abstract.",
    "authors": ["A. Author"],
    "categories": ["math.AG"],
}
SOURCE_DATE = date(2026, 11, 26)
EDITION = "2026-11-27"


def listing_section(name, identifier, showing=1, total=1):
    return (
        f'<h3>{name} (showing {showing} of {total} entries)</h3>'
        f'<dl><dt><a href="/abs/{identifier}">paper</a></dt>'
        '<dd><div class="list-title">Title: A paper</div></dd></dl>'
    )


class ListingTests(unittest.TestCase):
    def test_extracts_date_new_and_cross_listed_papers(self):
        html = '<h3>Showing new listings for Thursday, 26 November 2026</h3>'
        html += listing_section("New submissions", "2611.12345")
        html += listing_section("Cross submissions", "2611.12346")
        html += listing_section("Replacement submissions", "2611.00001")

        announced, papers = parse_listing(html, "math.AG")

        self.assertEqual(announced, SOURCE_DATE)
        self.assertEqual([paper["id"] for paper in papers], ["2611.12345", "2611.12346"])

    def test_rejects_incomplete_listing(self):
        html = '<h3>Showing new listings for Thursday, 26 November 2026</h3>'
        html += listing_section("New submissions", "2611.12345", total=2)
        with self.assertRaisesRegex(ValueError, "未显示完整列表"):
            parse_listing(html, "math.AG")


class PublicationTests(unittest.TestCase):
    def setUp(self):
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        self.root = Path(contexts.enter_context(tempfile.TemporaryDirectory()))
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.index = self.docs / "index.html"
        self.index.write_text("previous index", encoding="utf-8")
        self.tex = self.root / "latest.tex"
        self.tex.write_text("previous TeX", encoding="utf-8")
        self.state = self.root / "data" / "pipeline_state.json"
        contexts.enter_context(patch.multiple(pipeline, ROOT=self.root, DOCS=self.docs, STATE_FILE=self.state))
        contexts.enter_context(patch.object(pipeline, "set_output"))
        self.fetch = contexts.enter_context(
            patch.object(pipeline, "fetch_latest_issue", return_value=(SOURCE_DATE, {"math.AG": [PAPER]}))
        )
        self.args = Namespace(date=None, cache_dir=None, cache_output_dir=None, artifact_dir=None, test_mode=False)

    def test_duplicate_updates_check_time_without_running_ai(self):
        metadata = pipeline.issue_metadata(SOURCE_DATE, [PAPER])
        pipeline.write_json(self.state, {**metadata, "report_date": EDITION})
        report = self.docs / f"daily_{EDITION}.html"
        report.write_text("previous daily report", encoding="utf-8")

        def regenerate_index(script, flag, output_option, output_dir, time_option, timestamp, raw_dir):
            self.assertEqual((script, flag, output_option), ("generate_html.py", "--index-only", "--output-dir"))
            self.assertEqual(time_option, "--checked-at")
            self.assertTrue(timestamp.endswith("Z"))
            (output_dir / "index.html").write_text("checked index", encoding="utf-8")

        with patch.object(pipeline, "run_script", side_effect=regenerate_index) as run_script:
            pipeline.run(self.args)

        run_script.assert_called_once()
        self.assertEqual(self.index.read_text(encoding="utf-8"), "checked index")
        self.assertEqual(report.read_text(encoding="utf-8"), "previous daily report")
        self.assertEqual(self.tex.read_text(encoding="utf-8"), "previous TeX")

    def test_generation_failure_preserves_published_files(self):
        with patch.object(pipeline, "run_script", side_effect=subprocess.CalledProcessError(1, "AI")):
            with self.assertRaises(subprocess.CalledProcessError):
                pipeline.run(self.args)

        self.assertEqual(self.index.read_text(encoding="utf-8"), "previous index")
        self.assertEqual(self.tex.read_text(encoding="utf-8"), "previous TeX")
        self.assertFalse(self.state.exists())

    def test_rejects_cache_with_mismatched_papers(self):
        cache_dir = self.root / "cache"
        pipeline.write_json(cache_dir / pipeline.ISSUE_FILE, pipeline.issue_metadata(SOURCE_DATE, [PAPER]))
        pipeline.write_json(cache_dir / pipeline.PAPERS_FILE, [{**PAPER, "id": "2611.00000"}])
        self.args.cache_dir = cache_dir

        with self.assertRaisesRegex(ValueError, "源缓存与"):
            pipeline.run(self.args)

        self.fetch.assert_not_called()
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
