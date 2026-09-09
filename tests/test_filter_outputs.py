import csv
import ssl
import tempfile
import unittest
import warnings
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from law_crawler import LawCrawler, SSLAdapter
from run_filter import DifyError, run


class FilterOutputTests(unittest.TestCase):
    def test_ssl_without_legacy_constant(self):
        # Reproduce the Python 3.10 API even when tests run on newer Python.
        with patch.dict(ssl.__dict__):
            ssl.__dict__.pop("OP_LEGACY_SERVER_CONNECT", None)
            with warnings.catch_warnings():
                warnings.simplefilter("error", FutureWarning)
                adapter = SSLAdapter()
            try:
                self.assertTrue(adapter.ssl_context.options & 4)
                self.assertEqual(adapter.ssl_context.minimum_version, ssl.TLSVersion.TLSv1_2)
                self.assertEqual(adapter.ssl_context.maximum_version, ssl.TLSVersion.TLSv1_2)
            finally:
                adapter.close()

    def test_filtered_files_keep_publication_date_and_csv_quoting(self):
        published = date.today().isoformat()
        records = [
            dict(title='Law, "A"', source="Source, A", date=published, url="https://example.com/law"),
            dict(title="Case A", source="Court", date=published, url="https://example.com/case"),
            dict(title="News", date=published, url="https://example.com/news"),
            dict(title="Old law", date=(date.today() - timedelta(days=40)).isoformat()),
        ]

        def crawl(crawler):
            crawler.results = records
            crawler.case_results = [records[1]]

        agent = Mock()
        agent.classify.side_effect = ["law", "case", "other"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("run_filter.RESULT_OUTPUT_FILE", root / "result.txt"), \
                 patch("run_filter.LAW_OUTPUT_FILE", root / "law.txt"), \
                 patch("run_filter.CASE_OUTPUT_FILE", root / "case.txt"), \
                 patch.object(LawCrawler, "crawl_all", crawl):
                self.assertEqual(run(30, agent, file_date=date(2026, 1, 2)), (1, 1, 1))
            headers = ["\u6807\u9898", "\u6765\u6e90", "\u65e5\u671f", "\u94fe\u63a5", "\u6587\u4ef6\u65e5\u671f"]
            for name, record in zip(("law", "case"), records):
                with (root / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.reader(stream))
                expected = [record[k] for k in ("title", "source", "date", "url")] + ["2026-01-02"]
                self.assertEqual(rows, [headers, expected])
                txt = (root / f"{name}.txt").read_text(encoding="utf-8")
                self.assertEqual(txt, "".join(f"{label}\uff1a{value}\n" for label, value in zip(headers, expected)) + "\n")
            self.assertNotIn(headers[-1], (root / "result.txt").read_text(encoding="utf-8"))
            self.assertEqual(agent.classify.call_count, 3)
        self.assertNotIn("file_date", records[0])

    def test_default_generation_date_and_empty_csv(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        crawler.results = [dict(title="Example", date="2020-01-01")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            crawler.save_core_outputs(root / "law.txt", root / "case.txt")
            with (root / "law.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1][2], "2020-01-01")
            self.assertEqual(rows[1][4], date.today().isoformat())
            with (root / "case.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [rows[0]])
            self.assertEqual((root / "case.txt").read_text(encoding="utf-8"), "")

    def test_classification_failure_preserves_outputs(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        crawler.results = [dict(title="Example", date=date.today().isoformat())]
        crawler.crawl_all = Mock()
        crawler.save_items_file = Mock()
        crawler.save_core_outputs = Mock()
        agent = Mock()
        agent.classify.side_effect = DifyError("unavailable")
        with patch("run_filter.LawCrawler", return_value=crawler):
            with self.assertRaises(DifyError):
                run(30, agent)
        crawler.save_core_outputs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
