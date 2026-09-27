"""Public statement adapters. Fixed HTTPS origins, pinned public IP, no redirects."""

import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

MAX_PAGE = 2_000_000


def canonical_url(value):
    u = urlsplit(value.strip())
    if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
        raise ValueError("Use an HTTPS problem URL from Codeforces, AtCoder or CSES")
    host = u.hostname
    path = u.path.rstrip("/")
    patterns = {
        "codeforces.com": r"/(?:problemset/problem/\d+/[A-Za-z]\d*|contest/\d+/problem/[A-Za-z]\d*)",
        "atcoder.jp": r"/contests/[a-z0-9_-]+/tasks/[a-z0-9_-]+",
        "cses.fi": r"/problemset/task/\d+",
    }
    if host not in patterns or not re.fullmatch(patterns[host], path):
        raise ValueError("Unsupported problem URL")
    return (
        "https://"
        + host
        + path
        + (
            "?lang=en"
            if host == "atcoder.jp"
            else "?locale=en"
            if host == "codeforces.com"
            else "/"
        )
    )


def fetch_statement(url):
    u = urlsplit(canonical_url(url))
    addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
    ips = list(dict.fromkeys(row[4][0] for row in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Source resolved to a non-public address")
    conn = http.client.HTTPSConnection(
        u.hostname, timeout=8, context=ssl.create_default_context()
    )
    try:
        # Pin the checked address and retain certificate/hostname verification.
        raw = socket.create_connection((ips[0], 443), timeout=8)
        try:
            conn.sock = ssl.create_default_context().wrap_socket(
                raw, server_hostname=u.hostname
            )
        except Exception:
            raw.close()
            raise
        conn.request(
            "GET",
            u.path + ("?" + u.query if u.query else ""),
            headers={
                "User-Agent": "CodeArena statement importer",
                "Accept": "text/html",
                "Accept-Encoding": "identity",
            },
        )
        response = conn.getresponse()
        if (
            response.status != 200
            or "text/html" not in response.getheader("Content-Type", "")
            or response.getheader("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError(
                "Source refused the request. Save the public HTML page in your browser and import that file."
            )
        content = bytearray()
        deadline = time.monotonic() + 10
        while len(content) <= MAX_PAGE:
            if time.monotonic() > deadline:
                raise ValueError("Source request timed out")
            chunk = response.read1(min(65536, MAX_PAGE + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > MAX_PAGE:
            raise ValueError("Source page is too large")
        return bytes(content).decode("utf-8", errors="replace")
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError(
            "Could not load source; import a saved public HTML page instead"
        ) from exc
    finally:
        conn.close()


def parse_statement(url, html):
    url = canonical_url(url)
    if len(html.encode("utf-8")) > MAX_PAGE:
        raise ValueError("Source page is too large")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script,style,iframe,object,embed"):
        tag.decompose()
    host = urlsplit(url).hostname
    tests = []
    if host == "codeforces.com":
        root = soup.select_one(".problem-statement")
        title = root.select_one(".title") if root else None
        inputs = root.select(".sample-test .input pre") if root else []
        outputs = root.select(".sample-test .output pre") if root else []
    elif host == "atcoder.jp":
        root = soup.select_one("#task-statement .lang-en") or soup.select_one(
            "#task-statement"
        )
        title = soup.select_one(".h2")
        inputs = []
        outputs = []
        if root:
            for heading in root.find_all(["h3", "h2"]):
                sample = heading.find_next("pre")
                if heading and sample:
                    name = heading.get_text(" ", strip=True)
                    if re.match(r"(?:Sample Input|\u5165\u529b\u4f8b)\s*\d+", name):
                        inputs.append(sample)
                    elif re.match(r"(?:Sample Output|\u51fa\u529b\u4f8b)\s*\d+", name):
                        outputs.append(sample)
    else:
        root = soup.select_one(".content")
        title = soup.find("h1")
        pres = root.find_all("pre") if root else []
        inputs = pres[::2]
        outputs = pres[1::2]
    if not root or not title:
        raise ValueError(
            "Problem statement not found; login/challenge pages cannot be imported"
        )

    def sample_text(tag):
        for br in tag.find_all("br"):
            br.replace_with("\n")
        lines = tag.select(".test-example-line")
        return (
            "\n".join(x.get_text() for x in lines) if lines else tag.get_text()
        ).strip("\r\n") + "\n"

    for a, b in zip(inputs, outputs):
        tests.append(
            {
                "input_data": sample_text(a),
                "expected": sample_text(b),
                "is_sample": True,
                "weight": 1,
            }
        )
    if not tests or len(inputs) != len(outputs) or len(tests) > 50:
        raise ValueError(
            "Could not pair sample tests; add the statement and tests manually"
        )
    # Plain text only: no remote images, scripts, styles or arbitrary links are rendered.
    description = root.get_text("\n", strip=True)
    if len(description) > 28000:
        raise ValueError("Statement is too long; attach a document instead")
    text = root.get_text(" ", strip=True)
    seconds = re.search(
        r"(?:time limit per test|Time Limit:)\s*([\d.]+)\s*(?:second|sec)", text, re.I
    )
    memory = re.search(
        r"(?:memory limit per test|Memory Limit:)\s*(\d+)\s*(?:megabyte|MB|MiB)",
        text,
        re.I,
    )
    return {
        "title": title.get_text(" ", strip=True)[:200],
        "description": description + "\n\nSource: " + url,
        "time_limit": max(0.1, min(10, float(seconds[1]))) if seconds else 2,
        "mem_limit": max(32, min(512, int(memory[1]))) if memory else 256,
        "difficulty": "EASY",
        "tests": tests,
        "tags": [host.split(".")[0]],
        "source_url": url,
        "review_required": True,
    }
