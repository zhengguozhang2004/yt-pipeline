#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10: 从搜索结果页提取该书的全部详情链接，并逐个跟进
=====================================================

已经确认的事实：
  - libgen.li 搜索 "Motorcycle Dynamics Cossalter" 能搜到该书
  - 记录行: 'Motorcycle Dynamics Second Edition 1430308613; 9781430308614 b l 1509289'
  - edition.php?id=1509289 里有 md5 = 838e90ff2e4440c480e8832c47cabce5
  - 但 ads.php?md5= 页面无下载链接

本脚本：把结果行里所有 <a> 的 href 全部导出（含 title 链接、编辑链接、镜像链接），
并逐个请求，打印响应特征，找出真正的文件入口。
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
})

os.makedirs("results", exist_ok=True)
os.makedirs("out", exist_ok=True)
rep = {"query": QUERY, "rows": [], "probes": [], "files": []}


def log(m):
    print(str(m), flush=True)


def is_pdf(d):
    return len(d) > 10000 and d[:4] == b"%PDF"


def save(data, name):
    p = os.path.join("out", name)
    open(p, "wb").write(data)
    log("  >>> SAVED %s (%d bytes)" % (p, len(data)))
    rep["files"].append({"path": p, "bytes": len(data)})
    return p


HOSTS = ["libgen.li", "libgen.la", "libgen.bz"]


def find_target_row(host):
    """找到目标书的行并导出所有链接"""
    for params in ({"req": QUERY}, {"s": QUERY}):
        try:
            r = S.get("https://%s/index.php" % host, params=params, timeout=60)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for tb in soup.select("table#tablelibgen, table.c"):
                for tr in tb.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) < 3:
                        continue
                    first = tds[0].get_text(" ", strip=True)
                    if "Motorcycle Dynamics" not in first:
                        continue
                    # 收集该行所有链接
                    links = []
                    for a in tr.find_all("a", href=True):
                        links.append({
                            "text": a.get_text(" ", strip=True)[:40],
                            "href": a["href"],
                        })
                    log("\n[ROW] %s" % first[:100])
                    log("  links in row (%d):" % len(links))
                    for L in links:
                        log("    [%s] %s" % (L["text"], L["href"][:110]))
                    rep["rows"].append({"host": host, "row": first[:150], "links": links})
                    return links
        except Exception as e:
            log("  %s err %s" % (host, type(e).__name__))
    return None


def probe_links(links, host):
    """逐个跟进链接"""
    for L in links:
        href = L["href"]
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = "https://%s%s" % (host, href)
        elif href.startswith("http"):
            url = href
        else:
            url = "https://%s/%s" % (host, href)

        if "mailto:" in url or url.endswith(".css") or url.endswith(".js"):
            continue

        log("\n  FOLLOW %s" % url[:110])
        try:
            r = S.get(url, timeout=90, allow_redirects=True)
            ct = str(r.headers.get("content-type", ""))[:40]
            log("    -> %d %s len=%d magic=%r" % (r.status_code, ct, len(r.content), r.content[:6]))
            rep["probes"].append({"url": url, "status": r.status_code,
                                  "ctype": ct, "len": len(r.content)})

            if is_pdf(r.content):
                return save(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")

            if "octet" in ct and len(r.content) > 50000:
                return save(r.content, "book_raw.bin")

            if r.status_code == 200 and "html" in ct:
                soup = BeautifulSoup(r.text, "html.parser")
                sub = []
                for a in soup.find_all("a", href=True):
                    h = a["href"].strip()
                    low = h.lower()
                    if any(k in low for k in ("get.php", ".pdf", ".epub", ".djvu",
                                              "download", "/main/", "ipfs", "cdn")):
                        sub.append(h)
                log("    sub links: %d %s" % (len(sub), sub[:6]))
                for s in sub:
                    if s.startswith("//"):
                        su = "https:" + s
                    elif s.startswith("/"):
                        su = "https://%s%s" % (host, s)
                    elif s.startswith("http"):
                        su = s
                    else:
                        su = "https://%s/%s" % (host, s)
                    try:
                        log("      GET %s" % su[:100])
                        r2 = S.get(su, timeout=240, allow_redirects=True)
                        log("        -> %d len=%d magic=%r" % (
                            r2.status_code, len(r2.content), r2.content[:6]))
                        if is_pdf(r2.content):
                            return save(r2.content, "Motorcycle_Dynamics_2nd_Edition.pdf")
                    except Exception as e:
                        log("        err %s" % type(e).__name__)
        except Exception as e:
            log("    err %s" % type(e).__name__)

    return None


def main():
    log("=" * 64)
    log("v10: row-link extraction and follow")
    log("=" * 64)

    for host in HOSTS:
        log("\n##### HOST %s #####" % host)
        links = find_target_row(host)
        if not links:
            log("  no target row found")
            continue
        p = probe_links(links, host)
        if p:
            log("\n[SUCCESS] %s" % p)
            break

    with open("results/v10_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    log("\nwritten results/v10_report.json")
    return 0 if rep["files"] else 2


if __name__ == "__main__":
    sys.exit(main())