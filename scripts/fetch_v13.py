#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v13: 解析 get.php?md5= 返回的 HTML，找出最终下载链接
======================================================

v12 关键线索：
  get.php?md5=dd531d3b... -> 200 len=20670 magic=<!DO （这是 HTML 中转页）
  中转页里必然藏着指向真实文件（EPUB 34MB）的最终链接或 meta-refresh 跳转。

本脚本：抓该页面，保存原始 HTML，并提取：
  - meta http-equiv=refresh
  - 所有 <a href>
  - JS 里的 location.href / window.open
  - form action
"""

import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

REAL_MD5 = "dd531d3b702a951c8c899228e8ea8800"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

os.makedirs("results", exist_ok=True)
os.makedirs("out", exist_ok=True)
rep = {"md5": REAL_MD5, "pages": {}}


def log(m):
    print(str(m), flush=True)


HOSTS = ["libgen.li", "libgen.la", "libgen.bz", "libgen.vg"]


def analyze_get_page(host):
    url = "https://%s/get.php?md5=%s" % (host, REAL_MD5)
    log("\n===== %s =====" % url)
    try:
        r = S.get(url, timeout=60)
    except Exception as e:
        log("  err %s" % e)
        return

    log("  %d len=%d" % (r.status_code, len(r.content)))
    html = r.text

    # 保存原始页
    fn = "results/getpage_%s.html" % host.replace(".", "_")
    open(fn, "w", encoding="utf-8").write(html)
    log("  saved %s" % fn)

    # 1) meta refresh
    metas = re.findall(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']([^"\']+)["\']',
                       html, re.I)
    log("  meta refresh: %s" % metas)

    # 2) 所有链接，含 onclick
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        links.append(("a", a.get_text(" ", strip=True)[:30], a["href"]))

    # 3) JS 里的 URL
    js_urls = re.findall(r'(?:location\.href|window\.location|window\.open|href)\s*=\s*["\']([^"\']+)["\']',
                         html)
    js_urls2 = re.findall(r'(?:location\.replace)\s*\(\s*["\']([^"\']+)["\']', html)

    # 4) onclick 属性里的 URL
    onclick_urls = re.findall(r'onclick=["\'][^"\']*(?:location|href|open)\s*[=(]\s*["\']([^"\']+)["\']',
                              html, re.I)

    log("  <a> links: %d" % len(links))
    for tag, txt, h in links[:30]:
        log("    [%s|%s] %s" % (tag, txt, h[:110]))
    log("  js location urls: %s" % js_urls)
    log("  js replace urls: %s" % js_urls2)
    log("  onclick urls: %s" % onclick_urls)

    # 把所有疑似真实下载链接汇总
    all_candidates = js_urls + js_urls2 + onclick_urls + [h for _, _, h in links]
    rep["pages"][host] = {
        "status": r.status_code,
        "len": len(html),
        "meta_refresh": metas,
        "links": [h for _, _, h in links[:30]],
        "js_urls": js_urls + js_urls2,
        "onclick_urls": onclick_urls,
    }

    # 立即尝试 js 里的 URL 下载
    for u in js_urls + js_urls2 + onclick_urls:
        if not u.startswith("http"):
            u = "https://%s%s" % (host, u.lstrip("/"))
        try:
            r2 = S.get(u, timeout=180, allow_redirects=True, stream=True)
            ct = str(r2.headers.get("content-type", ""))[:30]
            cd = str(r2.headers.get("content-disposition", ""))[:80]
            log("  GET %s -> %d len=%d ctype=%s" % (u[:90], r2.status_code, len(r2.content), ct))
            log("      cd=%s magic=%r" % (cd, r2.content[:6]))
            if r2.status_code == 200 and len(r2.content) > 1000000:
                p = os.path.join("out", "Motorcycle_Dynamics_2nd_Edition.epub")
                open(p, "wb").write(r2.content)
                log("  >>> SAVED %s (%d bytes)" % (p, len(r2.content)))
                rep["files"] = [{"path": p, "bytes": len(r2.content)}]
                return True
        except Exception as e:
            log("  GET %s err %s" % (u[:80], type(e).__name__))
    return False


def main():
    log("=" * 64)
    log("v13: decode get.php redirect page")
    log("=" * 64)

    got = False
    for h in HOSTS:
        if analyze_get_page(h):
            got = True
            break

    with open("results/v13_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    log("\nwritten results/v13_report.json")
    return 0 if got else 2


if __name__ == "__main__":
    sys.exit(main())