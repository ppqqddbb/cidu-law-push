"""Send filtered cases using the Kingdee authentication protocol."""

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
from .file_dates import format_file_date


from .paths import CONFIG_DIR


DEFAULT_CONFIG = CONFIG_DIR / "kingdee.local.json"
DEFAULT_CASE_URL = "http://127.0.0.1:8881/ierp/kapi/v2/r8p0/r8p0_law/r8p0_case/case"
DEFAULT_TOKEN_URL = "http://127.0.0.1:8881/ierp/kapi/oauth2/getToken"


class KingdeeError(RuntimeError):
    """Authentication, transport or business-level API failure."""


def load_config(path=None):
    config_path = Path(path or os.getenv("KINGDEE_CONFIG", DEFAULT_CONFIG))
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict):
            raise ValueError("Kingdee config must be a JSON object")
    for key in ("token_url", "case_url", "client_id", "client_secret", "username",
                "account_id", "identity", "sync_kb"):
        value = os.getenv("KINGDEE_" + key.upper())
        if value is not None:
            config[key] = value
    config.setdefault("token_url", DEFAULT_TOKEN_URL)
    config.setdefault("case_url", DEFAULT_CASE_URL)
    return config


def build_case_payload(items, file_date=None, sync_kb="是"):
    """Map records to the seven fields accepted by the case API."""
    rows = []
    for item in items:
        published = str(item.get("date") or "").strip()
        generated = format_file_date(file_date if file_date is not None else item.get("file_date"))
        for label, value in (("date", published),):
            try:
                normalized = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
            except ValueError as exc:
                raise ValueError(f"Case {label} must be YYYY-MM-DD") from exc
            if value != normalized:
                raise ValueError(f"Case {label} must be YYYY-MM-DD")
        title = " ".join(str(item.get("title") or "").split())
        if not title:
            raise ValueError("Case title must not be empty")
        rows.append({
            "r8p0_title": title,
            "r8p0_source": str(item.get("source") or ""),
            "r8p0_link": str(item.get("url") or ""),
            "r8p0_date": published,
            "r8p0_file_date": generated,
            "r8p0_sync_kb": sync_kb,
            "r8p0_summary": str(item.get("summary") or ""),
        })
    return {"data": rows}


class KingdeeCaseClient:
    def __init__(self, config, timeout=60):
        self.config = config
        self.timeout = timeout
        if timeout <= 0:
            raise ValueError("Kingdee timeout must be positive")

    def _response_detail(self, response, body, url, headers):
        """Include the actual response shape without exposing credentials."""
        secrets = [self.config.get(key) for key in ("client_secret", "identity")]
        secrets.append(headers.get("access_token"))

        def clean(value, depth=0):
            if depth > 8:
                return "[truncated]"
            if isinstance(value, dict):
                return {str(key): "[redacted]" if re.search(
                    r"token|secret|password|authorization|cookie|identity", str(key), re.I
                ) else clean(item, depth + 1) for key, item in list(value.items())[:40]}
            if isinstance(value, list):
                return [clean(item, depth + 1) for item in value[:10]]
            if isinstance(value, str):
                for secret in secrets:
                    if isinstance(secret, str) and secret:
                        value = value.replace(secret, "[redacted]")
                value = re.sub(
                    r"(?i)((?:access_token|client_secret|password|authorization|x-acgw-identity)"
                    r"[\"\s:=]+)[^\s,;\"<>]+", r"\1[redacted]", value)
                return value[:1000]
            return value

        parts = urlsplit(url)
        endpoint = urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
        detail = {"httpStatus": response.status_code, "endpoint": endpoint,
                  "contentType": response.headers.get("Content-Type", ""), "response": body}
        return json.dumps(clean(detail), ensure_ascii=False, default=str)[:2500]

    def _post(self, session, url, payload, headers, operation):
        # Do not retry writes: a timeout can occur after the server commits data.
        try:
            response = session.post(url, json=payload, headers=headers,
                                    timeout=self.timeout, allow_redirects=False)
        except requests.RequestException:
            raise KingdeeError(f"{operation}: connection failed or timed out; "
                               "check server records before retrying") from None
        try:
            result = response.json()
        except ValueError:
            detail = self._response_detail(response, response.text, url, headers)
            raise KingdeeError(f"{operation}: response is not JSON; {detail}") from None
        detail = self._response_detail(response, result, url, headers)
        if not 200 <= response.status_code < 300:
            raise KingdeeError(f"{operation}: HTTP {response.status_code}; {detail}")
        if not isinstance(result, dict):
            raise KingdeeError(f"{operation}: response JSON must be an object; {detail}")

        # Kingdee responses use a JSON boolean in most deployments, but some
        # gateways serialize it as the string "true".  errorCode is returned
        # as the string "0" by the case API, so do not use truthiness here.
        status = result.get("status")
        status_ok = status is True or (isinstance(status, str) and status.strip().lower() == "true")
        error_code = result.get("errorCode")
        error_ok = error_code in (None, 0, "0", "")
        if not status_ok or not error_ok:
            reason = "unexpected response: missing top-level status" if "status" not in result else "API rejected request"
            raise KingdeeError(f"{operation}: {reason}; {detail}")
        data = result.get("data")
        if isinstance(data, dict):
            nested_success = data.get("success")
            nested_status = data.get("status")
            if nested_success is False or nested_status is False:
                raise KingdeeError(f"{operation}: business operation failed; {detail}")
            # The case endpoint reports per-record failures in `result`.
            errors = []
            rows = data.get("result", []) if isinstance(data.get("result"), list) else []
            for row in rows:
                if isinstance(row, dict) and row.get("billStatus") in (False, "false", "False"):
                    raise KingdeeError(f"{operation}: a case record was rejected; {detail}")
                if isinstance(row, dict) and row.get("errors"):
                    errors.extend(row["errors"] if isinstance(row["errors"], list) else [row["errors"]])
            if errors:
                raise KingdeeError(f"{operation}: business errors returned; {detail}")
            if operation == "Kingdee case push":
                for field in ("failCount", "successCount"):
                    if field not in data:
                        continue
                    value = data[field]
                    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
                        raise KingdeeError(f"{operation}: invalid {field}; {detail}")
                    count = int(value)
                    if (field == "failCount" and count != 0) or (
                            field == "successCount" and count != len(payload["data"])):
                        raise KingdeeError(f"{operation}: batch not fully accepted; {detail}")
        return result

    def send_cases(self, items, file_date=None, sync_kb=None):
        payload = build_case_payload(items, file_date,
                                     self.config.get("sync_kb", "是") if sync_kb is None else sync_kb)
        if not payload["data"]:
            return 0
        required = ("client_id", "client_secret", "username", "account_id")
        missing = [key for key in required if not self.config.get(key)]
        if missing:
            raise KingdeeError("Missing Kingdee configuration: " + ", ".join(missing))
        token_request = {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "username": self.config["username"],
            "accountId": self.config["account_id"],
            "nonce": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "language": "zh_CN",
        }
        with requests.Session() as session:
            result = self._post(session, self.config.get("token_url", DEFAULT_TOKEN_URL),
                                token_request, {"Content-Type": "application/json"}, "Kingdee token")
            data = result.get("data")
            token = data.get("access_token") if isinstance(data, dict) else None
            if not isinstance(token, str) or not token.strip():
                raise KingdeeError("Kingdee token: missing access_token")
            headers = {
                "Content-Type": "application/json",
                "access_token": token,
            }
            # Gateway identity is environment-specific; local deployments may
            # authenticate with just access_token.
            if self.config.get("identity"):
                headers["x-acgw-identity"] = self.config["identity"]
            self._post(session, self.config.get("case_url", DEFAULT_CASE_URL), payload,
                       headers, "Kingdee case push")
        return len(payload["data"])
