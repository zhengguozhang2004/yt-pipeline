#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5: 解析 libgen edition 页，找出真实的 md5 和下载链接
"""

import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

BOOK_ID = os.environ.get("BOOK_ID", "1509289").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
})

os.makedirs("out", exist_ok=True)
out = {"book_id": BOOK_ID, "hosts": {}}


def log(m):
    print(str(m), flush=True)


def save(data, name):
    p = os.path.join("out", name)
    with open(p, "wb") as f:
        f.write(data)
    log("SAVED %s (%d bytes)" % (p, len(data)))
    return p


HOSTS = ["libgen.li", "libgen.la", "libgen.bz"]


def probe_edition(host):
    url = f"https://{host}/edition.php?id={BOOK_ID}"
    log("\n===== %s =====" % url)
    try:
        r = S.get(url, timeout=45)
    except Exception as e:
        log("  err %s" % e)
        return

    log("  status=%d len=%d" % (r.status_code, len(r.content)))
    html = r.text

    # 保存原始页，便于分析
    with open(os.path.join("out", f"edition_{host}.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # 1) 找 32 位 md5
    md5s = re.findall(r"\b([0-9a-fA-F]{32})\b", html)
    log("  md5 candidates: %s" % list(dict.fromkeys(md5s))[:5])

    # 2) 找所有链接
    soup = BeautifulSoup(html, "html.parser")
    all_links = []
    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        t = a.get_text(" ", strip=True)[:40]
        if h and not h.startswith("#") and not h.startswith("javascript"):
            all_links.append((t, h))
    log("  total <a> links: %d" % len(all_links))
    for t, h in all_links[:40]:
        log("    [%s] %s" % (t, h[:110]))

    # 3) 找表格里的信息（大小/格式/扩展名）
    tables = soup.find_all("table")
    log("  tables: %d" % len(tables))
    for ti, tb in enumerate(tables[:4]):
        rows = tb.find_all("tr")
        log("    table[%d]: %d rows" % (ti, len(rows)))
        for tr in rows[:12]:
            cells = [td.get_text(" ", strip=True)[:40] for td in tr.find_all(["td", "th"])]
            if cells:
                log("      %s" % cells[:8])

    # 4) 找 data-* 属性 / onclick / JS 变量
    js_md5 = re.findall(r'(?:md5|MD5)["\']?\s*[:=]\s*["\']([0-9a-fA-F]{32})', html)
    log("  js md5: %s" % list(dict.fromkeys(js_md5))[:5])

    # 5) 找形如 /ads.php?md5= 的字符串
    direct = re.findall(r'(/ads\.php\?[a-zA-Z=]+[0-9a-fA-F]{32})', html)
    log("  ads.php refs: %s" % list(dict.fromkeys(direct))[:5])

    out["hosts"][host] = {
        "status": r.status_code,
        "len": len(html),
        "md5_candidates": list(dict.fromkeys(md5s))[:5],
        "link_count": len(all_links),
        "links": [{"text": t, "href": h} for t, h in all_links[:40]],
        "js_md5": list(dict.fromkeys(js_md5))[:5],
        "ads_refs": list(dict.fromkeys(direct))[:5],
    }


def main():
    log("===== v5 edition page probe =====")
    for h in HOSTS:
        probe_edition(h)

    with open("out/probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log("\nwritten out/probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())