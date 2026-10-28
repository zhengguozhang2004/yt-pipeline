#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端书籍获取器（运行在 GitHub Actions，境外 IP）
================================================

按通道优先级依次尝试，找到即停：
  C1  libgen.li      Search API + JSON
  C2  libgen.is / rs  Search + 下载镜像
  C3  Anna's Archive  fast download
  C4  archive.org    metadata API + 借阅
  C5  openlibrary    元数据
  C6  Google Books   元数据 + 预览

输出：
  out/fetch.log      完整日志
  out/report.json    结构化结果
  out/*.pdf/epub     下载到的文件
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

QUERY = os.environ.get("QUERY", "Motorcycle Dynamics Cossalter").strip()
MODE = os.environ.get("MODE", "search").strip()
ISBN = os.environ.get("ISBN", "").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
S = requests.Session()
S.headers.update(HEADERS)

os.makedirs("out", exist_ok=True)
report = {"query": QUERY, "isbn": ISBN, "mode": MODE, "attempts": [], "found": [], "files": []}


def log(m):
    line = str(m)
    print(line, flush=True)


def record(channel, ok, detail, extra=None):
    e = {"channel": channel, "ok": ok, "detail": detail}
    if extra:
        e["extra"] = extra
    report["attempts"].append(e)
    log(f"[{'OK ' if ok else 'FAIL'}] {channel}: {detail}")


# ---------------- C1: libgen.li ----------------

def try_libgen_li():
    log("\n===== C1 libgen.li =====")
    try:
        r = S.get(
            "https://libgen.li/index.php",
            params={"req": QUERY},
            timeout=30,
            allow_redirects=True,
        )
        log(f"  status={r.status_code} len={len(r.text)}")
        if r.status_code != 200:
            record("libgen.li", False, f"HTTP {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table.c tr")
        log(f"  table rows: {len(rows)}")

        items = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 9:
                continue
            try:
                title = tds[0].get_text(" ", strip=True)
                authors = tds[1].get_text(" ", strip=True)
                year = tds[4].get_text(" ", strip=True)
                ftype = tds[8].get_text(" ", strip=True)
                size = tds[7].get_text(" ", strip=True)
                mirrors = []
                for a in tds[9].find_all("a") if len(tds) > 9 else []:
                    href = a.get("href", "")
                    if href:
                        mirrors.append(href)
                items.append({
                    "title": title, "authors": authors, "year": year,
                    "type": ftype, "size": size, "mirrors": mirrors,
                })
            except Exception:
                continue

        log(f"  parsed items: {len(items)}")
        for it in items[:8]:
            log(f"    - {it['title'][:70]} | {it['authors'][:30]} | {it['year']} | {it['type']} | {it['size']}")

        if items:
            record("libgen.li", True, f"found {len(items)} results", {"items": items[:5]})
            report["found"].extend(items[:5])
            return items
        record("libgen.li", False, "no parsed rows")
        return None
    except Exception as e:
        record("libgen.li", False, f"{type(e).__name__}: {e}")
        return None


# ---------------- C2: libgen.is / .rs JSON API ----------------

def try_libgen_json(host):
    log(f"\n===== C2 {host} =====")
    try:
        r = S.get(
            f"https://{host}/search.php",
            params={"req": QUERY},
            timeout=30,
            allow_redirects=True,
        )
        log(f"  status={r.status_code} len={len(r.text)}")
        if r.status_code != 200:
            record(host, False, f"HTTP {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table.c tr")
        log(f"  table rows: {len(rows)}")

        items = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 8:
                continue
            try:
                items.append({
                    "title": tds[0].get_text(" ", strip=True),
                    "authors": tds[1].get_text(" ", strip=True),
                    "year": tds[4].get_text(" ", strip=True),
                    "type": tds[7].get_text(" ", strip=True),
                })
            except Exception:
                continue

        log(f"  parsed items: {len(items)}")
        for it in items[:8]:
            log(f"    - {it['title'][:70]} | {it['authors'][:30]} | {it['year']} | {it['type']}")

        if items:
            record(host, True, f"found {len(items)} results", {"items": items[:5]})
            report["found"].extend(items[:5])
            return items
        record(host, False, "no parsed rows")
        return None
    except Exception as e:
        record(host, False, f"{type(e).__name__}: {e}")
        return None


# ---------------- C3: Anna's Archive ----------------

def try_annas() -> object:
    log("\n===== C3 Anna's Archive =====")
    hosts = ["annas-archive.org", "annas-archive.se", "annas-archive.li"]
    for host in hosts:
        try:
            r = S.get(
                f"https://{host}/search",
                params={"q": QUERY},
                timeout=30,
                allow_redirects=True,
            )
            log(f"  {host} status={r.status_code} len={len(r.text)}")
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.select("a.js-vim-focus")
            if not links:
                links = soup.select("a[href*='/md5/']")
            log(f"  {host} links: {len(links)}")

            items = []
            for a in links[:10]:
                title = a.get_text(" ", strip=True)
                href = a.get("href", "")
                if title:
                    items.append({"title": title[:120], "href": href, "host": host})

            if items:
                for it in items[:8]:
                    log(f"    - {it['title'][:80]}")
                record("annas-archive", True, f"{host}: {len(items)} links", {"items": items[:5]})
                report["found"].extend(items[:5])
                return items
        except Exception as e:
            record(f"annas:{host}", False, f"{type(e).__name__}: {e}")
    record("annas-archive", False, "all hosts failed")
    return None


# ---------------- C4: archive.org ----------------

def try_archive_org():
    log("\n===== C4 archive.org =====")
    try:
        r = S.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f'title:("{QUERY}") OR description:("{QUERY}")',
                "fl[]": ["identifier", "title", "creator", "year"],
                "rows": 10,
                "output": "json",
            },
            timeout=30,
        )
        log(f"  status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            docs = d.get("response", {}).get("docs", [])
            log(f"  docs: {len(docs)}")
            for x in docs[:8]:
                log(f"    - {str(x.get('title'))[:70]} | {x.get('identifier')}")
            if docs:
                record("archive.org", True, f"{len(docs)} docs", {"items": docs[:5]})
                report["found"].extend(docs[:5])
                return docs
        record("archive.org", False, "no docs")
    except Exception as e:
        record("archive.org", False, f"{type(e).__name__}: {e}")
    return None


# ---------------- C5: openlibrary ----------------

def try_openlibrary():
    log("\n===== C5 openlibrary =====")
    try:
        r = S.get(
            "https://openlibrary.org/search.json",
            params={"q": QUERY, "limit": 5},
            timeout=30,
        )
        log(f"  status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            docs = d.get("docs", [])
            log(f"  docs: {len(docs)}")
            for x in docs[:5]:
                log(f"    - {str(x.get('title'))[:70]} | key={x.get('key')}")
            if docs:
                record("openlibrary", True, f"{len(docs)} docs", {"items": docs[:3]})
                return docs
        record("openlibrary", False, "no docs")
    except Exception as e:
        record("openlibrary", False, f"{type(e).__name__}: {e}")
    return None


# ---------------- C6: Google Books ----------------

def try_google_books():
    log("\n===== C6 Google Books =====")
    try:
        q = f"isbn:{ISBN}" if ISBN else QUERY
        r = S.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": q, "maxResults": 5},
            timeout=30,
        )
        log(f"  status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            items = d.get("items", [])
            log(f"  items: {len(items)}")
            for it in items[:5]:
                vi = it.get("volumeInfo", {})
                log(f"    - {str(vi.get('title'))[:60]} | {vi.get('publishedDate')} | pages={vi.get('pageCount')}")
                log(f"      preview: {it.get('accessInfo', {}).get('viewability')}")
                log(f"      link: {vi.get('infoLink')}")
            if items:
                record("google-books", True, f"{len(items)} items",
                       {"items": [{k: v.get("volumeInfo", {}).get(k) for k in ("title", "publishedDate", "pageCount", "authors")}
                                  for v in items[:3]]})
                return items
        record("google-books", False, "no items")
    except Exception as e:
        record("google-books", False, f"{type(e).__name__}: {e}")
    return None


# ---------------- 主流程 ----------------

def main():
    log("=" * 60)
    log("Cloud Book Fetcher (GitHub Actions)")
    log(f"  query : {QUERY}")
    log(f"  isbn  : {ISBN}")
    log(f"  mode  : {MODE}")
    log("=" * 60)

    # 元数据优先（方法论第 9 条：先攻元数据，后取内容）
    try_google_books()
    try_openlibrary()

    # 内容源
    try_libgen_li()
    try_libgen_json("libgen.is")
    try_libgen_json("libgen.rs")
    try_annas()
    try_archive_org()

    # 汇总
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    ok_channels = [a["channel"] for a in report["attempts"] if a["ok"]]
    log(f"successful channels: {ok_channels}")
    log(f"total results found: {len(report['found'])}")

    with open("out/report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log("written: out/report.json")

    return 0 if report["found"] else 2


if __name__ == "__main__":
    sys.exit(main())