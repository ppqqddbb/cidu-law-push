"""Dify agent classification and response parsing."""

import re
import time

import requests


class DifyError(RuntimeError):
    """Raised when the Dify agent cannot classify an item."""


class DifyAgent:
    def __init__(self, api_url: str, api_key: str, timeout: int = 60, retries: int = 2):
        self.endpoint = api_url.rstrip("/") + "/chat-messages"
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    def classify(self, item: dict) -> str:
        """Classify one crawl record with the configured Dify agent."""
        title = " ".join(str(item.get("title", "")).split())
        source = str(item.get("source", "")).strip()
        published = str(item.get("date", "")).strip()
        url = str(item.get("url", "")).strip()
        prompt = (
            "\u8bf7\u5bf9\u4e0b\u9762\u7684\u6cd5\u5f8b\u4fe1\u606f\u8fdb\u884c\u5206\u7c7b\uff0c"
            "\u53ea\u8fd4\u56de\u4e00\u4e2a\u82f1\u6587\u6807\u8bc6\uff1alaw\u3001case \u6216 other\u3002\n"
            f"\u5206\u7c7b\u89c4\u5219\uff1alaw=\u6cd5\u5f8b\u6761\u6587\uff1b"
            "case=\u6307\u5bfc\u6848\u4f8b\u6216\u88c1\u5224\u6587\u4e66\uff1b"
            "other=\u5176\u4ed6\u5185\u5bb9\u3002\n"
            f"\u6807\u9898\uff1a{title}\n\u6765\u6e90\uff1a{source}\n"
            f"\u65e5\u671f\uff1a{published}\n\u94fe\u63a5\uff1a{url}"
        )
        payload = {
            "inputs": {},
            "query": prompt,
            "response_mode": "blocking",
            "user": "law-push-filter",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.post(
                    self.endpoint, headers=headers, json=payload, timeout=self.timeout
                )
                if response.status_code != 200:
                    raise DifyError(f"HTTP {response.status_code}: {response.text[:500]}")
                category = parse_category(response.json().get("answer", ""))
                if category:
                    return category
                raise DifyError("agent returned an invalid category")
            except (requests.RequestException, ValueError, DifyError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise DifyError(f"failed to classify {title!r}: {last_error}")


def parse_category(answer: object) -> str | None:
    """Parse strict agent output, while tolerating a short Chinese response."""
    text = str(answer or "").strip().lower()
    exact = re.search(r"\b(law|case|other)\b", text)
    if exact:
        return exact.group(1)
    if "案例" in text or "裁判" in text or "判决" in text or "裁定" in text:
        return "case"
    if "法律" in text or "法规" in text or "规章" in text or "司法解释" in text:
        return "law"
    if "其他" in text:
        return "other"
    return None


