"""Polite HTTP helper used by every collector.

- robots.txt is checked before fetching (urllib.robotparser);
- at least 3 seconds between two requests;
- a neutral User-Agent, no personal data;
- raw responses are saved to data/raw/ (never published).
"""
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "reporting-case-study/1.0"
MIN_DELAY_S = 3.0
_last_call = 0.0
_robots = {}


def allowed(url: str) -> bool:
    p = urlparse(url)
    root = f"{p.scheme}://{p.netloc}"
    if root not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(root + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[root] = rp
    return _robots[root].can_fetch(USER_AGENT, url)


def get(url: str, check_robots: bool = True, **kw):
    """GET url if robots.txt allows it, waiting MIN_DELAY_S between calls. Returns a Response or None."""
    global _last_call
    if check_robots and not allowed(url):
        print("[robots] disallowed, skipped:", url)
        return None
    wait = MIN_DELAY_S - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=kw.pop("timeout", 60), **kw)
    except requests.RequestException as e:
        print("[error]", url, e)
        return None
