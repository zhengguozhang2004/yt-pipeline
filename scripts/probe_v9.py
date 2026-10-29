#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v9: libgen JSON API 正确用法 + 多源图书库
==========================================

libgen json.php 需要 object 参数，形式如：
  json.php?object=e&req=edition1&key=9781430308614
  json.php?object=l&req=<query>

同时并行尝试：
  - Z-Library 镜像
  - SciDB
  - library.lol
  - libgen.gs
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
S.headers.update({"User-Agent": UA,
                  "Accept": "application/json,text/html,*/*"})

os.makedirs("results", exist_ok=True)
report = {}


def log(m):
    print(str(m), flush=True)


def get(host, path, params=None, as_json=True):
    url = "https://%s%s" % (host, path)
    try:
        r = S.get(url, params=params, timeout=60)
        ct = str(r.headers.get("content-type", ""))[:30]
        log("  %s params=%s -> %d %s len=%d" % (url, params, r.status_code, ct, len(r.content)))
        if r.status_code != 200:
            return None
        if as_json:
            try:
                return r.json()
            except Exception:
                log("    (not json) %r" % r.text[:150])
                return None
        return r.text
    except Exception as e:
        log("  %s err %s" % (url, type(e).__name__))
        return None


HOSTS = ["libgen.li", "libgen.la", "libgen.bz"]

# ---------- 1. libgen json.php 正确参数 ----------

def probe_libgen_json():
    results = {}
    for h in HOSTS:
        log("\n===== %s json.php variants =====" % h)
        variants = [
            ("object=e&req=edition&key=" + ISBN, None),
            ("edition&key=" + ISBN, None),
            (None, {"object": "e", "req": "edition", "key": ISBN}),
            (None, {"req": "edition", "key": ISBN}),
            (None, {"object": "b", "req": "libinfo", "key": ISBN}),
            (None, {"object": "l", "req": QUERY}),
        ]
        for raw, params in variants:
            if raw:
                url = "https://%s/json.php?%s" % (h, raw)
                try:
                    r = S.get(url, timeout=45)
                    log("  GET %s -> %d len=%d" % (url[:100], r.status_code, len(r.content)))
                    if r.status_code == 200 and len(r.content) > 30:
                        try:
                            d = r.json()
                            log("    JSON: %s" % json.dumps(d, ensure_ascii=False)[:400])
                            results.setdefault(h, []).append({"url": url, "data": d})
                        except Exception:
                            log("    text: %r" % r.text[:200])
                except Exception as e:
                    log("    err %s" % type(e).__name__)
            else:
                d = get(h, "/json.php", params)
                if d:
                    results.setdefault(h, []).append({"params": params, "data": d})
    return results


# ---------- 2. 其他图书库 ----------

def probe_other_libs():
    out = {}
    log("\n===== other libraries =====")

    # Z-Library
    for h in ["z-library.se", "zh.z-lib.gs", "z-lib.io", "1lib.sk"]:
        log("  probe %s" % h)
        try:
            r = S.get("https://%s/" % h, timeout=20)
            log("    -> %d len=%d" % (r.status_code, len(r.content)))
            out[h] = r.status_code
        except Exception as e:
            log("    -> %s" % type(e).__name__)
            out[h] = type(e).__name__

    # library.lol
    log("  probe library.lol")
    try:
        r = S.get("https://library.lol/main/838e90ff2e4440c480e8832c47cabce5",
                  timeout=30, allow_redirects=True)
        log("    -> %d len=%d" % (r.status_code, len(r.content)))
        if r.status_code == 200:
            import re
            links = re.findall(r'href=["\']([^"\']*(?:get\.php|\.pdf|\.epub|\.djvu)[^"\']*)["\']',
                               r.text, re.I)
            log("    download links: %s" % links[:5])
            out["library.lol"] = {"status": 200, "links": links[:5]}
    except Exception as e:
        log("    -> %s" % type(e).__name__)
        out["library.lol"] = type(e).__name__

    return out


def main():
    log("=" * 64)
    log("v9: broad library probe")
    log("=" * 64)

    report["libgen_json"] = probe_libgen_json()
    report["other_libs"] = probe_other_libs()

    with open("results/v9_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log("\nwritten results/v9_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())