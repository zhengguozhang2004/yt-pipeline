#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7: 抓 ads 页面并原样保存，供离线分析下载链接形式"""

import json
import os
import re
import sys

import requests

MD5 = os.environ.get("BOOK_MD5", "838e90ff2e4440c480e8832c47cabce5").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

os.makedirs("out", exist_ok=True)
os.makedirs("results", exist_ok=True)

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def log(m):
    print(str(m), flush=True)


HOSTS = ["libgen.li", "libgen.la", "libgen.bz"]

summary = []

for host in HOSTS:
    url = "https://%s/ads.php?md5=%s" % (host, MD5)
    log("\n===== %s =====" % url)
    try:
        r = S.get(url, timeout=60)
        log("  %d len=%d" % (r.status_code, len(r.text)))

        # 保存原始 HTML 到 results/（会被提交到仓库）
        fn = "results/ads_%s.html" % host.replace(".", "_")
        with open(fn, "w", encoding="utf-8") as f:
            f.write(r.text)
        log("  saved %s" % fn)

        # 提取所有 http(s) 链接（含非 <a> 形式，如 JS 变量、iframe、form）
        urls = re.findall(r'https?://[^\s"\'<>]+', r.text)
        interesting = [u for u in urls if any(
            k in u.lower() for k in ("get.php", "download", ".pdf", ".epub", ".djvu",
                                     "library.lol", "libgen.rocks", "cdn", "file"))]
        log("  all urls: %d, interesting: %d" % (len(urls), len(interesting)))
        for u in list(dict.fromkeys(interesting))[:15]:
            log("    %s" % u[:120])

        # 找 form action
        forms = re.findall(r'<form[^>]*action=["\']([^"\']+)["\']', r.text, re.I)
        log("  forms: %s" % forms[:5])

        # 找 javascript 里的跳转
        js = re.findall(r'(?:location|href|window\.open)\s*[=(]\s*["\']([^"\']+)["\']', r.text)
        log("  js targets: %s" % js[:5])

        # 找 data 属性
        data_attrs = re.findall(r'data-[a-z-]+=["\']([^"\']{10,150})["\']', r.text)
        log("  data attrs: %s" % list(dict.fromkeys(data_attrs))[:8])

        summary.append({
            "host": host,
            "status": r.status_code,
            "len": len(r.text),
            "interesting": list(dict.fromkeys(interesting))[:15],
            "forms": forms[:5],
            "js": js[:5],
            "html_file": fn,
        })
    except Exception as e:
        log("  err %s: %s" % (type(e).__name__, e))
        summary.append({"host": host, "error": str(e)[:200]})

with open("results/ads_probe_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
log("\nwritten results/ads_probe_summary.json")