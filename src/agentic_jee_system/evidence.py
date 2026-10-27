"""Optional real search, with retained passages and source URLs."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pydantic import ValidationError
from .reliability import ServiceError, retry_call
from .schemas import Evidence


def authoritative(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    roots = ("ncert.nic.in", "nta.ac.in", "jeeadv.ac.in", "nptel.ac.in")
    return any(host == root or host.endswith("." + root) for root in roots) or host.endswith((".edu", ".ac.in"))


def retrieve(claims: list[str]) -> list[Evidence]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    body = json.dumps({"api_key": key, "query": "; ".join(claims)[:1500],
                       "max_results": 5, "search_depth": "basic"}).encode()

    def request():
        req = urllib.request.Request("https://api.tavily.com/search", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read(1_000_001)
                if len(data) > 1_000_000:
                    raise ServiceError("Search response exceeds the size limit.")
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            exc.status_code = exc.code
            exc.response = exc
            raise

    data = retry_call(request)
    evidence, seen = [], set()
    for item in data.get("results", [])[:5]:
        try:
            entry = Evidence(title=str(item.get("title", ""))[:200],
                             url=item.get("url", ""), excerpt=str(item.get("content", ""))[:2500])
        except ValidationError:
            continue
        if str(entry.url) not in seen:
            evidence.append(entry)
            seen.add(str(entry.url))
    return sorted(evidence, key=lambda entry: not authoritative(str(entry.url)))
