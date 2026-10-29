#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v6: 用已知 MD5 从 libgen 下载
==============================

已确认:
  ISBN : 9781430308614
  书名 : Motorcycle Dynamics Second Edition
  作者 : Vittore Cossalter / Lulu.com / 2006
  MD5  : 838e90ff2e4440c480e8832c47cabce5   <- 从 libgen.la edition 页提取
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

MD5 = os.environ.get("BOOK_MD5", "838e90ff2e4440c480e8832c47cabce5").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
})

os.makedirs("out", exist_ok=True)
rep = {"md5": MD5, "tried": [], "files": []}


def log(m):
    print(str(m), flush=True)


def save(data, name):
    p = os.path.join("out", name)
    with open(p, "wb") as f:
        f.write(data)
    log("  >>> SAVED %s (%d bytes)" % (p, len(data)))
    rep["files"].append({"path": p, "bytes": len(data)})
    return p


def is_pdf(d):
    return len(d) > 10000 and d[:4] == b"%PDF"


HOSTS = ["libgen.li", "libgen.la", "libgen.bz", "libgen.vg"]

# libgen 常见下载镜像前缀（ads.php 页面里的 "GET" 链接常指向这些）
MIRROR_PREFIXES = [
    "https://libgen.li/get.php?md5=",
    "https://libgen.la/get.php?md5=",
    "https://libgen.bz/get.php?md5=",
    "https://libgen.vg/get.php?md5=",
    "https://library.lol/main/",
    "https://libgen.rocks/get.php?md5=",
    "https://download.library.lol/main/",
]


def try_ads_host(host):
    url = "https://%s/ads.php?md5=%s" % (host, MD5)
    log("\n--- %s ---" % url)
    try:
        r = S.get(url, timeout=60, allow_redirects=True)
        ct = str(r.headers.get("content-type", ""))
        log("  %d ctype=%s len=%d" % (r.status_code, ct[:50], len(r.content)))

        if is_pdf(r.content):
            return save(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")

        if r.status_code != 200:
            return None

        with open(os.path.join("out", "ads_%s.html" % host), "w", encoding="utf-8") as f:
            f.write(r.text)

        soup = BeautifulSoup(r.text, "html.parser")
        cands = []
        for a in soup.find_all("a", href=True):
            h = a["href"].strip()
            t = a.get_text(" ", strip=True)
            low = h.lower()
            if any(k in low for k in ("get.php", "/main/", "download", ".pdf", ".epub", ".djvu")):
                if h.startswith("//"):
                    h = "https:" + h
                elif h.startswith("/"):
                    h = "https://%s%s" % (host, h)
                cands.append(h)
        log("  candidates: %d" % len(cands))
        for c in cands[:10]:
            log("    %s" % c[:110])
        rep["tried"].append({"url": url, "candidates": cands[:10]})

        for c in cands:
            try:
                log("  GET %s" % c[:100])
                r2 = S.get(c, timeout=240, allow_redirects=True)
                log("    %d ctype=%s len=%d magic=%r" % (
                    r2.status_code, str(r2.headers.get("content-type", ""))[:40],
                    len(r2.content), r2.content[:6]))
                if is_pdf(r2.content):
                    return save(r2.content, "Motorcycle_Dynamics_2nd_Edition.pdf")
            except Exception as e:
                log("    err %s" % type(e).__name__)
    except Exception as e:
        log("  err %s: %s" % (type(e).__name__, e))
    return None


def try_mirrors():
    log("\n===== direct mirror prefixes =====")
    for pref in MIRROR_PREFIXES:
        url = pref + MD5
        try:
            log("  GET %s" % url[:110])
            r = S.get(url, timeout=240, allow_redirects=True)
            log("    %d ctype=%s len=%d magic=%r" % (
                r.status_code, str(r.headers.get("content-type", ""))[:40],
                len(r.content), r.content[:6]))
            if is_pdf(r.content):
                return save(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")
            rep["tried"].append({"url": url, "status": r.status_code, "len": len(r.content)})
        except Exception as e:
            log("    err %s" % type(e).__name__)
    return None


def main():
    log("=" * 64)
    log("Cloud Book Downloader v6")
    log("  md5: %s" % MD5)
    log("=" * 64)

    p = try_mirrors()
    if p:
        log("\n[SUCCESS] %s" % p)
    else:
        for h in HOSTS:
            p = try_ads_host(h)
            if p:
                log("\n[SUCCESS] %s" % p)
                break

    with open("out/report6.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    return 0 if rep["files"] else 2


if __name__ == "__main__":
    sys.exit(main())