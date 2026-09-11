import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from law_push.kingdee import (DEFAULT_CASE_URL, KingdeeCaseClient, KingdeeError,
                         build_case_payload, load_config)
from law_push.crawler import LawCrawler
from law_push.case_push import read_cases
from law_push.pipeline import run


class KingdeeCaseTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(client_id="client", client_secret="secret", username="user",
                           account_id="account", identity="identity")
        self.item = dict(title="案例一", source="法院", url="https://example.com/case",
                         date="2026-08-01", file_date="2026-09-09", summary="案例摘要")

    def response(self, body, status=200):
        response = Mock(status_code=status, headers={"Content-Type": "application/json"}, text="not JSON")
        response.json.return_value = body
        return response

    def test_authentication_headers_and_exact_payload(self):
        session = Mock()
        session.post.side_effect = [
            self.response({"status": True, "data": {"access_token": "token"}}),
            self.response({"status": True, "data": {}}),
        ]
        with patch("law_push.kingdee.requests.Session") as factory:
            factory.return_value.__enter__.return_value = session
            self.assertEqual(KingdeeCaseClient(self.config).send_cases([self.item]), 1)
        token_call, case_call = session.post.call_args_list
        token_body = token_call.kwargs["json"]
        self.assertEqual(token_body["accountId"], "account")
        self.assertEqual(token_body["client_secret"], "secret")
        self.assertTrue(token_body["nonce"])
        self.assertTrue(token_body["timestamp"])
        self.assertEqual(case_call.args[0], DEFAULT_CASE_URL)
        self.assertEqual(case_call.kwargs["headers"]["access_token"], "token")
        self.assertEqual(case_call.kwargs["headers"]["x-acgw-identity"], "identity")
        self.assertEqual(case_call.kwargs["json"], {"data": [{
            "r8p0_title": "案例一", "r8p0_source": "法院", "r8p0_link": "https://example.com/case",
            "r8p0_date": "2026-08-01", "r8p0_file_date": "2026-09-09 00:00:00",
            "r8p0_sync_kb": "是", "r8p0_summary": "案例摘要",
        }]})
        self.assertEqual(case_call.kwargs["timeout"], 60)
        self.assertFalse(case_call.kwargs["allow_redirects"])

    def test_case_api_accepts_kingdee_success_response(self):
        session = Mock()
        session.post.side_effect = [
            self.response({"status": True, "data": {"access_token": "token"}}),
            self.response({"data": {"failCount": "0", "successCount": "1",
                                     "result": [{"billStatus": True, "errors": []}]},
                           "errorCode": "0", "message": None, "status": True}),
        ]
        with patch("law_push.kingdee.requests.Session") as factory:
            factory.return_value.__enter__.return_value = session
            self.assertEqual(KingdeeCaseClient(self.config).send_cases([self.item]), 1)

    def test_case_api_reports_record_errors(self):
        session = Mock()
        session.post.side_effect = [
            self.response({"status": True, "data": {"access_token": "token"}}),
            self.response({"status": True, "errorCode": "0",
                           "data": {"result": [{"errors": ["invalid title"]}]}}),
        ]
        with patch("law_push.kingdee.requests.Session") as factory:
            factory.return_value.__enter__.return_value = session
            with self.assertRaises(KingdeeError) as caught:
                KingdeeCaseClient(self.config).send_cases([self.item])
            self.assertIn("invalid title", str(caught.exception))

    def test_missing_status_shows_gateway_response_without_credentials(self):
        session = Mock()
        session.post.return_value = self.response({
            "code": "AUTH_FAILED", "msg": "invalid access_token=live-token",
            "nested": {"access_token": "another-token", "client_secret": "secret"},
            "description": "supplied live-token with identity",
        })
        client = KingdeeCaseClient(self.config)
        with self.assertRaises(KingdeeError) as caught:
            client._post(session, DEFAULT_CASE_URL, {"data": [self.item]},
                         {"access_token": "live-token"}, "Kingdee case push")
        message = str(caught.exception)
        self.assertIn("missing top-level status", message)
        self.assertIn("AUTH_FAILED", message)
        self.assertIn('"httpStatus": 200', message)
        self.assertIn(DEFAULT_CASE_URL, message)
        for sensitive in ("live-token", "another-token", '"secret"'):
            self.assertNotIn(sensitive, message)

    def test_partial_failures_are_not_reported_as_success(self):
        bodies = [
            {"failCount": "1", "successCount": "0"},
            {"failCount": "1", "successCount": "1"},
            {"successCount": "0"},
            {"successCount": "not a count"},
            {"result": [{"billStatus": False, "errors": []}]},
        ]
        for data in bodies:
            with self.subTest(data=data):
                session = Mock()
                session.post.return_value = self.response({"status": True, "errorCode": "0", "data": data})
                with self.assertRaises(KingdeeError):
                    KingdeeCaseClient(self.config)._post(
                        session, DEFAULT_CASE_URL, {"data": [self.item]}, {}, "Kingdee case push")

    def test_http_and_non_json_errors_include_diagnostics(self):
        for response in (self.response({"code": "Unauthorized"}, 401),
                         self.response({}, 502)):
            if response.status_code == 502:
                response.json.side_effect = ValueError()
                response.text = "gateway failure client_secret=secret"
            session = Mock()
            session.post.return_value = response
            with self.assertRaises(KingdeeError) as caught:
                KingdeeCaseClient(self.config)._post(session, DEFAULT_CASE_URL, {}, {}, "Kingdee case push")
            self.assertIn(str(response.status_code), str(caught.exception))
            self.assertNotIn("=secret", str(caught.exception))

    def test_empty_batch_skips_authentication(self):
        with patch("law_push.kingdee.requests.Session") as session:
            self.assertEqual(KingdeeCaseClient({}).send_cases([]), 0)
            session.assert_not_called()

    def test_local_authentication_without_gateway_identity(self):
        config = dict(self.config, token_url="http://127.0.0.1:8881/ierp/kapi/oauth2/getToken",
                      client_id="case", username="local-user", account_id="local-account")
        config.pop("identity")
        with patch("law_push.kingdee.requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.post.side_effect = [
                self.response({"status": True, "data": {"access_token": "local-token"}}),
                self.response({"status": True, "errorCode": "0", "data": {
                    "successCount": "1", "failCount": "0"}}),
            ]
            self.assertEqual(KingdeeCaseClient(config).send_cases([self.item]), 1)
        token_call, case_call = session.post.call_args_list
        self.assertEqual(token_call.args[0], config["token_url"])
        self.assertEqual(token_call.kwargs["json"]["client_id"], "case")
        self.assertEqual(token_call.kwargs["json"]["accountId"], "local-account")
        self.assertEqual(token_call.kwargs["json"]["username"], "local-user")
        self.assertNotIn("x-acgw-identity", case_call.kwargs["headers"])
        self.assertEqual(case_call.kwargs["headers"]["access_token"], "local-token")

    def test_authentication_failure_does_not_send_cases(self):
        for result in ({"status": False}, {"status": True, "data": {}}, []):
            with self.subTest(result=result), patch("law_push.kingdee.requests.Session") as factory:
                session = factory.return_value.__enter__.return_value
                session.post.return_value = self.response(result)
                with self.assertRaises(KingdeeError):
                    KingdeeCaseClient(self.config).send_cases([self.item])
                self.assertEqual(session.post.call_count, 1)

    def test_api_failures_and_timeouts_are_not_retried(self):
        invalid_json = self.response({})
        invalid_json.json.side_effect = ValueError("invalid JSON")
        for failure in (self.response({}, 500), self.response({"status": False}),
                        self.response({"status": True, "data": {"success": False}}),
                        invalid_json, requests.Timeout("secret-token")):
            with self.subTest(failure=failure), patch("law_push.kingdee.requests.Session") as factory:
                session = factory.return_value.__enter__.return_value
                session.post.side_effect = [
                    self.response({"status": True, "data": {"access_token": "token"}}), failure]
                with self.assertRaises(KingdeeError) as caught:
                    KingdeeCaseClient(self.config).send_cases([self.item])
                self.assertNotIn("secret-token", str(caught.exception))
                self.assertEqual(session.post.call_count, 2)

    def test_file_date_validation_and_overrides(self):
        record = dict(self.item)
        record.pop("file_date")
        record.pop("summary")
        with self.assertRaises(ValueError):
            build_case_payload([record])
        payload = build_case_payload([record], "2026-09-10", "否")["data"][0]
        self.assertEqual(payload["r8p0_file_date"], "2026-09-10 00:00:00")
        self.assertEqual(payload["r8p0_sync_kb"], "否")
        self.assertEqual(payload["r8p0_summary"], "")
        with self.assertRaises(ValueError):
            build_case_payload([record], "2026-02-30")

    def test_generated_txt_and_csv_can_be_sent(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        crawler.results = crawler.case_results = [self.item]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("txt", "csv"):
                crawler.save_core_outputs(root / "law.txt", root / f"case.{suffix}", "2026-09-09")
                payload = build_case_payload(read_cases(root / f"case.{suffix}"))
                self.assertEqual(payload["data"][0]["r8p0_title"], self.item["title"])
                self.assertEqual(payload["data"][0]["r8p0_file_date"], "2026-09-09 00:00:00")

    def test_filter_only_pushes_cases_after_files_saved(self):
        crawler = LawCrawler(days=30)
        self.addCleanup(crawler.session.close)
        case = dict(self.item, date=date.today().isoformat())
        law = dict(case, title="Law", url="https://example.com/law")
        crawler.results = [law, case]
        crawler.case_results = [case]
        crawler.crawl_all = Mock()
        crawler.save_items_file = Mock()
        agent = Mock()
        agent.classify.side_effect = ["law", "case"]
        client = Mock()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def send(items, generated, sync_kb):
                self.assertEqual(items, [case])
                self.assertEqual(generated, "2026-09-10 00:00:00")
                self.assertTrue((root / "case.csv").exists())
                self.assertTrue((root / "law.txt").exists())
                raise KingdeeError("push failed")

            client.send_cases.side_effect = send
            with patch("law_push.pipeline.LawCrawler", return_value=crawler), \
                 patch("law_push.pipeline.LAW_OUTPUT_FILE", root / "law.txt"), \
                 patch("law_push.pipeline.CASE_OUTPUT_FILE", root / "case.csv"):
                with self.assertRaises(KingdeeError):
                    run(30, agent, file_date=date(2026, 9, 10), case_client=client)
            self.assertFalse((root / "case.txt").exists())
            self.assertTrue((root / "case.csv").exists())

    def test_config_environment_overrides_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "law_push.settings.json"
            path.write_text(json.dumps(self.config), encoding="utf-8")
            with patch.dict("os.environ", {"KINGDEE_CASE_URL": "http://example.com/case"}, clear=True):
                config = load_config(path)
            self.assertEqual(config["case_url"], "http://example.com/case")
            self.assertEqual(config["client_id"], "client")


if __name__ == "__main__":
    unittest.main()
