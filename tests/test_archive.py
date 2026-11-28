import tempfile
import unittest
from pathlib import Path

from scripts import generate_html


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.docs = Path(temporary.name)

    def write_report(self, date, canonical=None, papers=1):
        filename = f"daily_{date}.html"
        link = f"<link href='{canonical}' rel='canonical'>" if canonical else ""
        (self.docs / filename).write_text(
            f"<html><head>{link}</head><body>"
            f'<div class="counter-category">总计</div><div class="counter-value">{papers}</div>'
            "</body></html>",
            encoding="utf-8",
        )
        return filename

    def test_rebuild_lists_canonical_report_with_superseded_date(self):
        canonical = self.write_report("2026-11-27", papers=47)
        old_report = self.write_report("2026-11-26", canonical, papers=46)

        self.assertTrue(generate_html.generate_index_html(output_dir=self.docs))
        index = (self.docs / "index.html").read_text(encoding="utf-8")

        self.assertEqual(index.count('class="date-card"'), 1)
        self.assertIn('data-date="2026-11-27" data-alias-dates="2026-11-26"', index)
        self.assertIn(f'href="{canonical}" class="date-link"', index)
        self.assertIn("47 篇论文", index)
        self.assertNotIn(f'href="{old_report}"', index)
        self.assertTrue((self.docs / old_report).is_file())

    def test_invalid_or_missing_canonicals_leave_report_visible(self):
        self.write_report("2026-11-27")
        self.write_report("2026-11-26", "https://example.com/daily_2026-11-27.html")
        self.write_report("2026-11-25", "../daily_2026-11-27.html")
        self.write_report("2026-11-24", "daily_2026-11-23.html")
        self.write_report("2026-11-22", "daily_2026-11-31.html")
        self.write_report("2026-11-31")

        reports = generate_html.scan_existing_daily_files(self.docs)
        self.assertEqual([report["date"].day for report in reports], [27, 26, 25, 24, 22])
        self.assertTrue(all(not report["alias_dates"] for report in reports))

    def test_aliases_resolve_to_final_report_but_cycles_remain_visible(self):
        final = self.write_report("2026-11-27")
        middle = self.write_report("2026-11-26", f"./{final}")
        self.write_report("2026-11-25", middle)
        self.write_report("2026-11-24", "daily_2026-11-23.html")
        self.write_report("2026-11-23", "daily_2026-11-24.html")
        self.write_report("2026-11-22", "daily_2026-11-24.html")

        reports = generate_html.scan_existing_daily_files(self.docs)
        self.assertEqual([report["date"].day for report in reports], [27, 24, 23, 22])
        self.assertEqual(sorted(day.day for day in reports[0]["alias_dates"]), [25, 26])
        self.assertTrue(all(not report["alias_dates"] for report in reports[1:]))


if __name__ == "__main__":
    unittest.main()
