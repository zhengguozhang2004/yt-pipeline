#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v11: 深入正确的文件页，拿到真实下载链接并下载
================================================

v10 关键发现：
  - 真实 MD5:   dd531d3b702a951c8c899228e8ea8800
  - file.php:   file.php?id=92540206  -> 200, 26110 字节
  - edition.php: edition.php?id=137286556 -> 200, 28973 字节

本脚本：请求 file.php 页面，提取真实的 GET 链接（指向 libgen 存储/CDN），
下载 PDF 并校验。
"""

import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

REAL_MD5 = os.environ.get("REAL_MD5", "dd531d3b702a951c8c899228e8ea8800").strip()
FILE_ID = os.environ.get("FILE_ID", "92540206").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
})

os.makedirs("out", exist_ok=True)
os.makedirs("results", exist_ok=True)
rep = {"md5": REAL_MD5, "file_id": FILE_ID, "probes": [], "files": []}


def log(m):
    print(str(m), flush=True)


def save(data, name):
    p = os.path.join("out", name)
    open(p, "wb").write(data)
    log("  >>> SAVED %s (%d bytes)" % (p, len(data)))
    rep["files"].append({"path": p, "bytes": len(data)})
    return p


def is_pdf(d):
    return len(d) > 10000 and d[:4] == b"%PDF"


HOSTS = ["libgen.li", "libgen.la", "libgen.bz", "libgen.vg"]

# 已知的真实下载端点模式（libgen 世界通用的 /get.php?md5=）
MIRROR_HOSTS = [
    "libgen.rocks", "libgen.li", "libgen.la", "libgen.bz", "libgen.vg",
    "libgen.gs", "libgen.pm", "libgen.is", "libgen.rs", "libgen.st",
    "download.library.lol", "library.lol", "libgen.fun",
]


def try_file_page(host):
    """请求 file.php 页，提取 GET 链接"""
    url = "https://%s/file.php?id=%s" % (host, FILE_ID)
    log("\n--- %s ---" % url)
    try:
        r = S.get(url, timeout=60)
        ct = str(r.headers.get("content-type", ""))
        log("  %d %s len=%d" % (r.status_code, ct[:40], len(r.content)))

        if is_pdf(r.content):
            return save(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")

        if r.status_code != 200:
            return None

        # 保存原始页
        open(os.path.join("results", "file_%s.html" % host.replace(".", "_")),
             "w", encoding="utf-8").write(r.text)

        soup = BeautifulSoup(r.text, "html.parser")

        # 收集所有下载相关的链接和 form
        cands = []
        for a in soup.find_all("a", href=True):
            h = a["href"].strip()
            t = a.get_text(" ", strip=True)[:40]
            low = h.lower()
            if any(k in low for k in ("get.php", ".pdf", ".epub", ".djvu",
                                      "download", "/main/", "ipfs", "cdn", "file")):
                if h.startswith("//"):
                    h = "https:" + h
                elif h.startswith("/"):
                    h = "https://%s%s" % (host, h)
                cands.append((t, h))

        log("  candidate links: %d" % len(cands))
        for t, h in cands[:20]:
            log("    [%s] %s" % (t, h[:110]))
        rep["probes"].append({"url": url, "candidates": [h for _, h in cands[:20]]})

        for t, h in cands:
            try:
                log("  GET %s" % h[:100])
                r2 = S.get(h, timeout=300, allow_redirects=True)
                log("    -> %d len=%d magic=%r" % (
                    r2.status_code, len(r2.content), r2.content[:6]))
                if is_pdf(r2.content):
                    return save(r2.content, "Motorcycle_Dynamics_2nd_Edition.pdf")
            except Exception as e:
                log("    err %s" % type(e).__name__)

    except Exception as e:
        log("  err %s: %s" % (type(e).__name__, e))
    return None


def try_direct_mirrors():
    """直接尝试所有镜像的 get.php?md5=REAL_MD5"""
    log("\n===== direct get.php?md5 mirrors =====")
    for h in MIRROR_HOSTS:
        url = "https://%s/get.php?md5=%s" % (h, REAL_MD5)
        try:
            r = S.get(url, timeout=60, allow_redirects=True)
            log("  %s -> %d len=%d magic=%r" % (h, r.status_code, len(r.content), r.content[:6]))
            if is_pdf(r.content):
                return save(r.content, "Motorcycle_Dynamics_2nd_Edition.pdf")
        except Exception as e:
            log("  %s -> %s" % (h, type(e).__name__))
    return None


def main():
    log("=" * 64)
    log("v11: real download")
    log("  real md5: %s" % REAL_MD5)
    log("=" * 64)

    p = try_direct_mirrors()
    if not p:
        for h in HOSTS:
            p = try_file_page(h)
            if p:
                break

    with open("results/v11_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    log("\nwritten results/v11_report.json")
    return 0 if rep["files"] else 2


if __name__ == "__main__":
    sys.exit(main())