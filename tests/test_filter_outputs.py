import csv
import ssl
import tempfile
import unittest
import warnings
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from law_push.crawler import LawCrawler, SSLAdapter
from law_push.pipeline import DifyError, run


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
            with patch("law_push.pipeline.RESULT_OUTPUT_FILE", root / "result.txt"), \
                 patch("law_push.pipeline.LAW_OUTPUT_FILE", root / "law.txt"), \
                 patch("law_push.pipeline.CASE_OUTPUT_FILE", root / "case.csv"), \
                 patch.object(LawCrawler, "crawl_all", crawl):
                self.assertEqual(run(30, agent, file_date=date(2026, 1, 2), import_database=False), (1, 1, 1))
            headers = ["\u6807\u9898", "\u6765\u6e90", "\u65e5\u671f", "\u94fe\u63a5", "\u6587\u4ef6\u65e5\u671f"]
            with (root / "case.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            expected = [records[1][k] for k in ("title", "source", "date", "url")] + ["2026-01-02 00:00:00"]
            self.assertEqual(rows, [headers, expected])
            expected = [records[0][k] for k in ("title", "source", "date", "url")] + ["2026-01-02 00:00:00"]
            txt = (root / "law.txt").read_text(encoding="utf-8")
            self.assertEqual(txt, "".join(f"{label}\uff1a{value}\n" for label, value in zip(headers, expected)) + "\n")
            self.assertFalse((root / "law.csv").exists())
            self.assertFalse((root / "case.txt").exists())
            self.assertNotIn(headers[-1], (root / "result.txt").read_text(encoding="utf-8"))
            self.assertEqual(agent.classify.call_count, 3)
        self.assertNotIn("file_date", records[0])

    def test_default_generation_date_and_empty_csv(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        crawler.results = [dict(title="Example", date="2020-01-01")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            crawler.save_core_outputs(root / "law.txt", root / "case.csv")
            text = (root / "law.txt").read_text(encoding="utf-8")
            self.assertIn("日期：2020-01-01", text)
            self.assertIn(f"文件日期：{date.today().isoformat()} ", text)
            with (root / "case.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [["标题", "来源", "日期", "链接", "文件日期"]])
            self.assertFalse((root / "case.txt").exists())

    def test_classification_failure_preserves_outputs(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        crawler.results = [dict(title="Example", date=date.today().isoformat())]
        crawler.crawl_all = Mock()
        crawler.save_items_file = Mock()
        crawler.save_core_outputs = Mock()
        agent = Mock()
        agent.classify.side_effect = DifyError("unavailable")
        with patch("law_push.pipeline.LawCrawler", return_value=crawler):
            with self.assertRaises(DifyError):
                run(30, agent)
        crawler.save_core_outputs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
