#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8: 用 libgen 的 JSON API 查询记录的真实状态
============================================

关键判断：搜索结果里该书记录是 "b l"（book + libinfo），
libinfo 记录常只有元数据无文件。必须查 JSON API 确认真实文件和 md5。

API 端点（libgen）：
  https://libgen.li/json.php?req=edition&isbn=<isbn>
  https://libgen.li/json.php?req=libinfo&isbn=<isbn>
  https://libgen.li/json.php?req=<search>
"""

import json
import os
import sys

import requests

ISBN = os.environ.get("ISBN", "9781430308614").strip()
QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json,text/html,*/*"})

os.makedirs("out", exist_ok=True)
os.makedirs("results", exist_ok=True)

HOSTS = ["libgen.li", "libgen.la", "libgen.bz", "libgen.vg"]
report = {}


def log(m):
    print(str(m), flush=True)


def try_json(host, req):
    url = "https://%s/json.php" % host
    try:
        r = S.get(url, params={"req": req}, timeout=60)
        log("\n--- %s?req=%s" % (url, req))
        log("    %d ctype=%s len=%d" % (
            r.status_code, str(r.headers.get("content-type", ""))[:40], len(r.content)))
        if r.status_code != 200 or len(r.content) < 20:
            return None
        try:
            data = r.json()
        except Exception:
            log("    not json, first 200: %r" % r.text[:200])
            return None

        if isinstance(data, list):
            log("    items: %d" % len(data))
            for it in data[:6]:
                if isinstance(it, dict):
                    keys = ["id", "md5", "title", "author", "extension", "filesize",
                            "edition", "year", "publisher", "descr", "toc", "pages"]
                    brief = {k: it.get(k) for k in keys if k in it}
                    log("      %s" % json.dumps(brief, ensure_ascii=False)[:300])
        elif isinstance(data, dict):
            log("    dict keys: %s" % list(data.keys())[:15])
            log("    %s" % json.dumps(data, ensure_ascii=False)[:400])

        return data
    except Exception as e:
        log("    err %s: %s" % (type(e).__name__, e))
        return None


def main():
    log("=" * 64)
    log("v8: libgen JSON API probe")
    log("  isbn : %s" % ISBN)
    log("  query: %s" % QUERY)
    log("=" * 64)

    for host in HOSTS:
        for req in ("edition", "libinfo"):
            data = try_json(host, req)
            if data:
                report.setdefault(host, {})[req] = data

    # 再试一次搜索式 API
    for host in HOSTS:
        for req in ("search", QUERY):
            pass

    with open("results/json_probe.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log("\nwritten results/json_probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())