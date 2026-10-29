#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端书籍下载器（v3）—— 从 libgen.li 下载指定记录
=================================================

已知目标：
  记录 ID : 1509289
  ISBN    : 1430308613 / 9781430308614
  书名    : Motorcycle Dynamics Second Edition
  作者    : Vittore Cossalter
  出版社  : Lulu.com (2006)

流程：
  1. libgen.li ads.php?md5=<MD5>  -> 获取下载页
  2. 从下载页提取真实下载链接
  3. 下载文件到 out/
  4. 校验（大小/类型/PDF结构）
"""

import hashlib
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

MD5_OR_ID = os.environ.get("BOOK_ID", "1509289").strip()
QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

os.makedirs("out", exist_ok=True)
report = {"book_id": MD5_OR_ID, "query": QUERY, "steps": [], "files": []}


def log(m):
    print(str(m), flush=True)


def step(name, ok, detail):
    report["steps"].append({"step": name, "ok": ok, "detail": str(detail)[:500]})
    log(f"[{'OK ' if ok else 'FAIL'}] {name}: {str(detail)[:200]}")


HOSTS = ["libgen.li", "libgen.la", "libgen.vg", "libgen.bz", "libgen.onl", "libgen.ee"]


def find_md5():
    """通过搜索页拿到目标记录的 MD5"""
    for h in HOSTS:
        try:
            r = S.get(f"https://{h}/index.php", params={"req": QUERY}, timeout=40)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for tr in soup.select("table#tablelibgen tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                first = tds[0].get_text(" ", strip=True)
                if "Motorcycle Dynamics Second Edition" in first:
                    # 该行的链接里通常有 md5=xxxx
                    md5 = None
                    for a in tds[0].find_all("a"):
                        href = a.get("href", "")
                        m = re.search(r"md5=([0-9a-fA-F]{32})", href)
                        if m:
                            md5 = m.group(1).lower()
                            break
                    # 或者用 id 参数
                    if not md5:
                        m = re.search(r"id=(\d+)", first)
                    log(f"  matched row on {h}: md5={md5}")
                    step("find_row", True, {"host": h, "md5": md5, "row": first[:120]})
                    return h, md5
            log(f"  {h}: no matching row (len={len(r.text)})")
        except Exception as e:
            log(f"  {h} error: {type(e).__name__}")
    step("find_row", False, "no host yielded target row")
    return None, None


def try_download(host, md5):
    """尝试多种 URL 形态下载"""
    urls = []
    if md5:
        urls += [
            f"https://{host}/ads.php?md5={md5}",
            f"https://{host}/get.php?md5={md5}",
        ]

    for u in urls:
        try:
            log(f"\n  GET {u}")
            r = S.get(u, timeout=60, allow_redirects=True)
            log(f"    status={r.status_code} ctype={r.headers.get('content-type')} len={len(r.content)}")

            # 直接是文件？
            ct = str(r.headers.get("content-type", ""))
            cd = str(r.headers.get("content-disposition", ""))
            if ("octet-stream" in ct or "pdf" in ct or "download" in cd) and len(r.content) > 100000:
                name = "book.pdf"
                m = re.search(r'filename="?([^";]+)"?', cd)
                if m:
                    name = m.group(1).strip()
                path = os.path.join("out", name)
                with open(path, "wb") as f:
                    f.write(r.content)
                log(f"    SAVED {path} ({len(r.content)} bytes)")
                step("download", True, {"url": u, "file": path, "bytes": len(r.content)})
                report["files"].append({"path": path, "bytes": len(r.content)})
                return path

            # 是 HTML 页面 -> 找真实链接
            soup = BeautifulSoup(r.text, "html.parser")
            cands = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                txt = a.get_text(" ", strip=True)
                if any(k in href.lower() for k in ("get.php", "download", ".pdf", "libgen")):
                    cands.append((href, txt))
            log(f"    html page, candidate links: {len(cands)}")
            for href, txt in cands[:8]:
                log(f"      {txt[:40]!r} -> {href[:100]}")

            # 取第一个看起来像下载的
            for href, txt in cands:
                if "get.php" in href or href.lower().endswith(".pdf"):
                    full = href if href.startswith("http") else f"https://{host}/{href.lstrip('/')}"
                    log(f"    trying {full}")
                    r2 = S.get(full, timeout=180, allow_redirects=True, stream=True)
                    log(f"      status={r2.status_code} ctype={r2.headers.get('content-type')}")
                    if r2.status_code == 200:
                        data = r2.content
                        if len(data) > 100000 and data[:4] == b"%PDF":
                            path = os.path.join("out", "Motorcycle_Dynamics_2nd_Ed.pdf")
                            with open(path, "wb") as f:
                                f.write(data)
                            log(f"      SAVED {path} ({len(data)} bytes) VALID PDF")
                            step("download", True, {"url": full, "file": path, "bytes": len(data)})
                            report["files"].append({"path": path, "bytes": len(data)})
                            return path
                        log(f"      not a PDF (first bytes: {data[:20]!r})")
        except Exception as e:
            log(f"    error: {type(e).__name__}: {e}")

    step("download", False, "all urls failed")
    return None


def main():
    log("=" * 62)
    log("Cloud Book Downloader v3")
    log(f"  book_id: {MD5_OR_ID}")
    log(f"  query  : {QUERY}")
    log("=" * 62)

    host, md5 = find_md5()
    if host and md5:
        path = try_download(host, md5)
        if path:
            with open("out/report3.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return 0

    with open("out/report3.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log("\nno file downloaded")
    return 2


if __name__ == "__main__":
    sys.exit(main())