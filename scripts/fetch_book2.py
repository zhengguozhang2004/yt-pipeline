#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端书籍获取器 v2 —— 更广的通道覆盖
====================================

v1 教训：
  - libgen.is/.rs 在 Actions 上超时
  - annas-archive.org/.se DNS 已死（需要新域名）
  - libgen.li 结构变了，需要换解析方式

v2 增加：
  - libgen 新镜像族（.la .gs .vg .bz .onl）
  - Anna's Archive 新域名
  - Google Books 换 API 参数
  - 搜索引擎（DuckDuckGo html 版，Actions 上可用）
  - SciDB / Zlib 镜像探测
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()
ISBN = os.environ.get("ISBN", "9781430308614").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})

os.makedirs("out", exist_ok=True)
report = {"query": QUERY, "isbn": ISBN, "attempts": [], "found": []}


def log(m):
    print(str(m), flush=True)


def rec(ch, ok, detail, extra=None):
    e = {"channel": ch, "ok": ok, "detail": str(detail)[:400]}
    if extra:
        e["extra"] = extra
    report["attempts"].append(e)
    log(f"[{'OK ' if ok else 'FAIL'}] {ch}: {str(detail)[:180]}")


def probe(host, scheme="https"):
    """快速探测主机可达性"""
    try:
        r = S.get(f"{scheme}://{host}", timeout=15, allow_redirects=True)
        return r.status_code
    except Exception as e:
        return f"{type(e).__name__}"


# ---------- 1. libgen 镜像族探测 ----------

LIBGEN_HOSTS = [
    "libgen.li", "libgen.la", "libgen.gs", "libgen.vg", "libgen.bz",
    "libgen.onl", "libgen.lc", "libgen.fun", "libgen.is", "libgen.rs",
    "libgen.st", "libgen.ee",  "libgen.click",
]


def try_libgen_family():
    log("\n===== libgen mirror family =====")
    live = []
    for h in LIBGEN_HOSTS:
        st = probe(h)
        log(f"  {h:16} -> {st}")
        if st == 200:
            live.append(h)

    if not live:
        rec("libgen-family", False, "no live hosts")
        return None

    for h in live:
        log(f"\n  --- searching on {h} ---")
        for params in (
            {"req": QUERY},
            {"s": QUERY},
        ):
            try:
                r = S.get(f"https://{h}/index.php", params=params, timeout=30)
                log(f"    {h} {params} -> {r.status_code} len={len(r.text)}")
                if r.status_code != 200 or len(r.text) < 500:
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                # 尝试多种表格结构
                for sel in ("table.c tr", "table#tablelibgen tr", "tr"):
                    rows = soup.select(sel)
                    items = []
                    for tr in rows:
                        tds = tr.find_all("td")
                        if len(tds) < 6:
                            continue
                        txts = [td.get_text(" ", strip=True) for td in tds]
                        # 找包含 Dynamics 的行
                        joined = " ".join(txts).lower()
                        if "dynamic" in joined or "cossalter" in joined:
                            items.append({"cells": txts[:10], "host": h})
                    if items:
                        log(f"    * {sel}: {len(items)} matching rows")
                        for it in items[:5]:
                            log(f"      - {it['cells'][:4]}")
                        rec(f"libgen:{h}", True, f"{len(items)} rows", {"items": items[:5]})
                        report["found"].extend(items[:5])
                        return items
            except Exception as e:
                log(f"    {h} error: {type(e).__name__}: {e}")
    rec("libgen-family", False, "live hosts but no results parsed")
    return None


# ---------- 2. Anna's Archive 新域名 ----------

ANNAS_HOSTS = [
    "annas-archive.li", "annas-archive.se", "annas-archive.org",
    "annasarchive.org", "annas-archive.gs", "annas-archive.pm",
]


def try_annas2():
    log("\n===== Anna's Archive (new domains) =====")
    for h in ANNAS_HOSTS:
        st = probe(h)
        log(f"  {h:22} -> {st}")
        if st != 200:
            continue
        try:
            r = S.get(f"https://{h}/search", params={"q": QUERY}, timeout=30)
            log(f"    search -> {r.status_code} len={len(r.text)}")
            soup = BeautifulSoup(r.text, "html.parser")
            items = []
            for a in soup.select("a[href*='/md5/']"):
                t = a.get_text(" ", strip=True)
                if t:
                    items.append({"title": t[:140], "href": a.get("href"), "host": h})
            log(f"    items: {len(items)}")
            for it in items[:6]:
                log(f"      - {it['title'][:90]}")
            if items:
                rec("annas", True, f"{h}: {len(items)}", {"items": items[:5]})
                report["found"].extend(items[:5])
                return items
        except Exception as e:
            log(f"    {h} error: {type(e).__name__}")
    rec("annas", False, "no results")
    return None


# ---------- 3. DuckDuckGo HTML 搜索 ----------

def try_ddg():
    log("\n===== DuckDuckGo HTML =====")
    queries = [
        f'"{QUERY}" pdf',
        f'"Motorcycle Dynamics" Cossalter filetype:pdf',
        f'Cossalter "Motorcycle Dynamics" download',
    ]
    for q in queries:
        try:
            r = S.post("https://html.duckduckgo.com/html/",
                       data={"q": q}, timeout=30)
            log(f"  q={q[:50]!r} -> {r.status_code} len={len(r.text)}")
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for a in soup.select("a.result__a"):
                href = a.get("href", "")
                title = a.get_text(" ", strip=True)
                if title:
                    results.append({"title": title[:140], "href": href})
            log(f"  results: {len(results)}")
            for x in results[:8]:
                log(f"    - {x['title'][:80]}")
                log(f"      {x['href'][:100]}")
            if results:
                rec("duckduckgo", True, f"{len(results)} results", {"items": results[:5]})
                report["found"].extend(results[:5])
                return results
        except Exception as e:
            log(f"  ddg error: {type(e).__name__}: {e}")
    rec("duckduckgo", False, "no results")
    return None


# ---------- 4. Google Books 精确查询 ----------

def try_gbooks():
    log("\n===== Google Books (exact) =====")
    for q in [f"isbn:{ISBN}", f'intitle:"Motorcycle Dynamics" inauthor:Cossalter', "Motorcycle Dynamics Cossalter"]:
        try:
            r = S.get("https://www.googleapis.com/books/v1/volumes",
                      params={"q": q, "maxResults": 10}, timeout=30)
            log(f"  q={q[:50]!r} -> {r.status_code}")
            if r.status_code != 200:
                continue
            d = r.json()
            items = d.get("items", [])
            log(f"  items: {len(items)}")
            keep = []
            for it in items:
                vi = it.get("volumeInfo", {})
                ai = it.get("accessInfo", {})
                title = str(vi.get("title", ""))
                if "motorcycle" in title.lower() or "dynamics" in title.lower():
                    keep.append({
                        "title": title,
                        "authors": vi.get("authors"),
                        "date": vi.get("publishedDate"),
                        "pages": vi.get("pageCount"),
                        "preview": ai.get("viewability"),
                        "epub_avail": (ai.get("epub") or {}).get("isAvailable"),
                        "pdf_avail": (ai.get("pdf") or {}).get("isAvailable"),
                        "link": vi.get("infoLink"),
                        "id": it.get("id"),
                    })
            for k in keep[:6]:
                log(f"    - {k['title'][:50]} | {k['date']} | pages={k['pages']} | {k['preview']} | pdf={k['pdf_avail']}")
            if keep:
                rec("google-books", True, f"{len(keep)} relevant", {"items": keep})
                report["found"].extend(keep)
                return keep
        except Exception as e:
            log(f"  gbooks error: {type(e).__name__}")
    rec("google-books", False, "no relevant items")
    return None


# ---------- 5. archive.org 全文搜索 ----------

def try_archive2():
    log("\n===== archive.org (expanded) =====")
    queries = [
        f'title:("Motorcycle Dynamics")',
        f'creator:("Cossalter")',
        f'"Motorcycle Dynamics"',
    ]
    for q in queries:
        try:
            r = S.get("https://archive.org/advancedsearch.php", params={
                "q": q,
                "fl[]": ["identifier", "title", "creator", "year", "mediatype"],
                "rows": 10,
                "output": "json",
            }, timeout=30)
            log(f"  q={q[:40]!r} -> {r.status_code}")
            if r.status_code != 200:
                continue
            docs = r.json().get("response", {}).get("docs", [])
            log(f"  docs: {len(docs)}")
            for x in docs[:8]:
                log(f"    - {str(x.get('title'))[:60]} | {x.get('identifier')} | {x.get('mediatype')}")
            if docs:
                rec("archive.org", True, f"{len(docs)} docs", {"items": docs[:5]})
                report["found"].extend(docs[:5])
                return docs
        except Exception as e:
            log(f"  archive error: {type(e).__name__}")
    rec("archive.org", False, "no docs")
    return None


# ---------- 6. 作者/大学官网探测（关系层） ----------

def try_author_site():
    log("\n===== Author / university site =====")
    urls = [
        "https://www.dinamoto.it/",
        "https://www.dinamoto.it/DINAMOTO/moto/index.html",
        "http://www.dinamoto.it/",
        "https://www.gest.unipd.it/",
        "https://www.unipd.it/en/",
    ]
    found = []
    for u in urls:
        try:
            r = S.get(u, timeout=20, allow_redirects=True)
            log(f"  {u} -> {r.status_code} len={len(r.text)}")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text(" ", strip=True).lower()
                has = "motorcycle" in text or "cossalter" in text or "dinamica" in text
                log(f"    contains motorcycle/cossalter: {has}")
                # 找 PDF 链接
                pdfs = [a.get("href") for a in soup.find_all("a", href=True)
                        if str(a.get("href", "")).lower().endswith(".pdf")]
                log(f"    pdf links: {len(pdfs)}")
                for p in pdfs[:5]:
                    log(f"      {p}")
                found.append({"url": u, "status": r.status_code, "has_content": has,
                              "pdfs": pdfs[:10]})
        except Exception as e:
            log(f"  {u} -> {type(e).__name__}")
    if found:
        rec("author-site", True, f"{len(found)} reachable", {"items": found})
    else:
        rec("author-site", False, "none reachable")
    return found


def main():
    log("=" * 62)
    log("Cloud Book Fetcher v2")
    log(f"  query: {QUERY}")
    log(f"  isbn : {ISBN}")
    log("=" * 62)

    try_gbooks()
    try_ddg()
    try_libgen_family()
    try_annas2()
    try_archive2()
    try_author_site()

    log("\n" + "=" * 62)
    log("SUMMARY")
    log("=" * 62)
    oks = [a["channel"] for a in report["attempts"] if a["ok"]]
    log("successful:", oks)
    log("total found:", len(report["found"]))

    with open("out/report2.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log("written: out/report2.json")
    return 0 if report["found"] else 2


if __name__ == "__main__":
    sys.exit(main())