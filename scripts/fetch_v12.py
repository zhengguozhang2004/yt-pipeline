#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v12: 用真实 MD5 + 更多 IPFS 网关 + libgen 存储路径直接下载 EPUB
==============================================================

已知：
  MD5       = dd531d3b702a951c8c899228e8ea8800
  IPFS CID  = bafykbzacebduug3k744h3qwnp3b4vlvfanshctrngh5b567qxmkm4oagneghc
  文件名    = Motorcycle Dynamics{Vittore Cossalter}(2006, Lulu.com){137286556}.epub
  大小      = 34702984 字节

libgen 存储路径规律（onion 里可见）：
  /LG/01509000/dd531d3b702a951c8c899228e8ea8800/<文件名>

所以镜像站的存储路径大概率是：
  https://<镜像>/LG/01509000/dd531d3b.../<文件名>
或 libgen 的直连 CDN。

本脚本穷举：
  1. 多家 IPFS 公共网关（dweb.link, ipfs.io, cloudflare-ipfs 等）
  2. libgen 各种镜像的 /LG/ 静态存储路径
  3. download.library.lol 的 main/<md5> 路径
"""

import json
import os
import sys

import requests

REAL_MD5 = "dd531d3b702a951c8c899228e8ea8800"
CID = "bafykbzacebduug3k744h3qwnp3b4vlvfanshctrngh5b567qxmkm4oagneghc"
FNAME = "Motorcycle Dynamics{Vittore Cossalter}(2006, Lulu.com){137286556}.epub"
FNAME_ENC = FNAME.replace(" ", "%20").replace("{", "%7B").replace("}", "%7D") \
                 .replace("(", "%28").replace(")", "%29").replace(",", "%2C")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

os.makedirs("out", exist_ok=True)
os.makedirs("results", exist_ok=True)
rep = {"tried": [], "files": []}


def log(m):
    print(str(m), flush=True)


def save(data, name):
    p = os.path.join("out", name)
    open(p, "wb").write(data)
    log("  >>> SAVED %s (%d bytes)" % (p, len(data)))
    rep["files"].append({"path": p, "bytes": len(data)})
    return p


def is_book(d):
    # EPUB 以 PK (zip) 开头，PDF 以 %PDF 开头
    return len(d) > 100000 and (d[:4] == b"%PDF" or d[:2] == b"PK")


# ---------- IPFS 网关 ----------

IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://ipfs.dweb.link/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://nftstorage.link/ipfs/",
    "https://ipfs.fleek.co/ipfs/",
    "https://w3s.link/ipfs/",
    "https://4everland.io/ipfs/",
    "https://ipfs.eth.aragon.network/ipfs/",
]


def try_ipfs():
    log("\n===== IPFS gateways =====")
    for gw in IPFS_GATEWAYS:
        url = gw + CID
        try:
            r = S.get(url, timeout=120, allow_redirects=True, stream=True)
            log("  %s -> %d len=%d" % (gw[:45], r.status_code, len(r.content)))
            rep["tried"].append({"type": "ipfs", "url": url, "status": r.status_code,
                                 "len": len(r.content)})
            if r.status_code == 200 and is_book(r.content):
                return save(r.content, "Motorcycle_Dynamics_2nd_Edition.epub")
        except Exception as e:
            log("  %s -> %s" % (gw[:45], type(e).__name__))
    return None


# ---------- libgen 静态存储 /LG/ 路径 ----------

LIBGEN_STORAGE_HOSTS = [
    "libgen.li", "libgen.la", "libgen.bz", "libgen.vg", "libgen.gs",
    "libgen.pm", "libgen.is", "libgen.rs", "libgen.st", "libgen.fun",
    "libgen.rocks", "cdn1.booksdl.org", "libgen.io",
]


def try_libgen_storage():
    log("\n===== libgen /LG/ storage paths =====")
    dirnum = "01509000"
    for h in LIBGEN_STORAGE_HOSTS:
        # 三种路径形态
        urls = [
            "https://%s/LG/%s/%s/%s" % (h, dirnum, REAL_MD5, FNAME_ENC),
            "https://%s/LG/%s/%s" % (h, dirnum, REAL_MD5),
            "https://%s/main/%s" % (h, REAL_MD5),
            "https://%s/get.php?md5=%s" % (h, REAL_MD5),
        ]
        for u in urls:
            try:
                r = S.get(u, timeout=90, allow_redirects=True, stream=True)
                log("  %s -> %d len=%d magic=%r" % (u[:80], r.status_code, len(r.content), r.content[:4]))
                rep["tried"].append({"type": "storage", "url": u, "status": r.status_code,
                                     "len": len(r.content)})
                if r.status_code == 200 and is_book(r.content):
                    return save(r.content, "Motorcycle_Dynamics_2nd_Edition.epub")
            except Exception as e:
                log("  %s -> %s" % (u[:80], type(e).__name__))
    return None


# ---------- download.library.lol ----------

def try_library_lol():
    log("\n===== library.lol =====")
    urls = [
        "https://download.library.lol/main/%s" % REAL_MD5,
        "https://library.lol/main/%s" % REAL_MD5,
        "https://libgen.lol/main/%s" % REAL_MD5,
    ]
    for u in urls:
        try:
            r = S.get(u, timeout=120, allow_redirects=True, stream=True)
            log("  %s -> %d len=%d magic=%r" % (u[:70], r.status_code, len(r.content), r.content[:4]))
            rep["tried"].append({"type": "library.lol", "url": u, "status": r.status_code,
                                 "len": len(r.content)})
            if r.status_code == 200 and is_book(r.content):
                return save(r.content, "Motorcycle_Dynamics_2nd_Edition.epub")
        except Exception as e:
            log("  %s -> %s" % (u[:70], type(e).__name__))
    return None


def main():
    log("=" * 64)
    log("v12: final download attempt")
    log("  md5 : %s" % REAL_MD5)
    log("  cid : %s" % CID)
    log("=" * 64)

    p = None
    p = p or try_ipfs()
    p = p or try_libgen_storage()
    p = p or try_library_lol()

    with open("results/v12_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    log("\nwritten results/v12_report.json")
    return 0 if rep["files"] else 2


if __name__ == "__main__":
    sys.exit(main())