#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端书籍下载器 v4
=================

v3 教训：libgen.li 的搜索结果行里，链接是 ads.php?id=<ID> 而不是 md5，
        解析 md5 失败导致无法下载。

v4 策略：直接用记录 ID 拼出所有可能的下载端点，逐个尝试。
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BOOK_ID = os.environ.get("BOOK_ID", "1509289").strip()
QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
})

os.makedirs("out", exist_ok=True)
report = {"book_id": BOOK_ID, "steps": [], "files": [], "links": []}


def log(m):
    print(str(m), flush=True)


def step(name, ok, detail):
    report["steps"].append({"step": name, "ok": ok, "detail": str(detail)[:800]})
    log(f"[{'OK ' if ok else 'FAIL'}] {name}: {str(detail)[:250]}")


HOSTS = ["libgen.li", "libgen.la", "libgen.vg", "libgen.bz", "libgen.onl", "libgen.ee"]


def save_file(data, name):
    path = os.path.join("out", name)
    with open(path, "wb") as f:
        f.write(data)
    log(f"  SAVED {path} ({len(data)} bytes)")
    report["files"].append({"path": path, "bytes": len(data)})
    return path


def is_pdf(data):
    return len(data) > 10000 and data[:4] == b"%PDF"


def extract_links(html, host):
    """从广告页提取真实下载链接"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        txt = a.get_text(" ", strip=True)
        low = href.lower()
        if not href or href.startswith("#") or low.startswith("javascript"):
            continue
        if any(k in low for k in ("get.php", "download", ".pdf", ".epub", ".djvu",
                                   "libgen.li/get", "books.ms", "library.lol",
                                   "cdn", "file")):
            if href.startswith("http"):
                out.append(href)
            elif href.startswith("//"):
                out.append("https:" + href)
            else:
                out.append(f"https://{host}/{href.lstrip('/')}")
    # 去重保序
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq, [a.get_text(" ", strip=True)[:40] for a in soup.find_all("a", href=True)]


def try_host(host, book_id):
    log(f"\n===== host: {host} =====")
    endpoints = [
        f"https://{host}/ads.php?id={book_id}",
        f"https://{host}/ads.php?md5={book_id}",
        f"https://{host}/edition.php?id={book_id}",
        f"https://{host}/book/index.php?md5={book_id}",
        f"https://{host}/get.php?id={book_id}",
        f"https://{host}/get.php?md5={book_id}",
    ]

    for ep in endpoints:
        try:
            log(f"  GET {ep}")
            r = S.get(ep, timeout=45, allow_redirects=True)
            ct = str(r.headers.get("content-type", ""))
            cd = str(r.headers.get("content-disposition", ""))
            log(f"    -> {r.status_code} ctype={ct[:60]} len={len(r.content)}")

            if is_pdf(r.content):
                log("    !! DIRECT PDF")
                return save_file(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")

            if "octet-stream" in ct and len(r.content) > 10000:
                return save_file(r.content, "book_download.bin")

            if r.status_code != 200 or len(r.content) < 500:
                continue

            links, texts = extract_links(r.text, host)
            log(f"    candidate links: {len(links)}")
            for L in links[:12]:
                log(f"      {L[:110]}")
            report["links"].extend({"endpoint": ep, "link": L} for L in links[:12])

            for L in links:
                try:
                    log(f"    TRY {L[:100]}")
                    r2 = S.get(L, timeout=180, allow_redirects=True, stream=True)
                    c2 = str(r2.headers.get("content-type", ""))
                    n2 = r2.headers.get("content-length")
                    log(f"      -> {r2.status_code} ctype={c2[:50]} len={n2}")
                    if r2.status_code != 200:
                        continue
                    data = r2.content
                    log(f"      got {len(data)} bytes, magic={data[:8]!r}")
                    if is_pdf(data):
                        log("      !! VALID PDF")
                        return save_file(data, "Motorcycle_Dynamics_2nd_Edition.pdf")
                except Exception as e:
                    log(f"      err {type(e).__name__}")
        except Exception as e:
            log(f"    endpoint err: {type(e).__name__}: {e}")

    return None


def main():
    log("=" * 64)
    log("Cloud Book Downloader v4")
    log(f"  book_id: {BOOK_ID}")
    log(f"  query  : {QUERY}")
    log("=" * 64)

    for h in HOSTS:
        try:
            path = try_host(h, BOOK_ID)
            if path:
                step("download", True, {"host": h, "file": path})
                with open("out/report4.json", "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                return 0
        except Exception as e:
            log(f"host {h} fatal: {e}")

    step("download", False, "all hosts/endpoints failed")
    with open("out/report4.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return 2


if __name__ == "__main__":
    sys.exit(main())