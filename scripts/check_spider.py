#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验每个源配置里的 spider（解析器 jar）是否真的可以下载。

spider 是 TVBox 的解析器。取不到就意味着：站点列表能显示，但点开播放必炸。
这比配置 404 更隐蔽 —— 页面看起来一切正常，用户点进去才发现全废。

除了能否下载，还看**快慢**：raw.githubusercontent.com 在国内经常能连通
但慢到 20~45 秒，TVBox 加载超时后一样算失败。所以这里分三档：
  ok     < FAST_SECONDS
  slow   >= FAST_SECONDS 但能下完
  dead   下载失败

用法：
  python scripts/check_spider.py            # 检查 output/ 现有产物
  python scripts/check_spider.py --url URL  # 检查单个 jar 地址
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")

SKIP = {"多仓订阅.json", "单仓聚合.json", "status.json", "shield.json"}
UA = "Mozilla/5.0"
FAST_SECONDS = 8.0      # 超过这个时长对 TVBox 来说基本等于不可用
TIMEOUT = 45            # 给慢站留足时间，避免把"慢"误判成"死"


def probe_once(url):
    """单次尝试，返回 (state, seconds, note)。"""
    started = time.time()
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT,
                         allow_redirects=True, stream=True)
        status = r.status_code
        total = int(r.headers.get("Content-Length") or 0)
        # 只读首块确认可下载即可。之前读到 2MB 才停，对刚好在边界附近的
        # 文件会白等几十秒，把好源误判成慢源。
        chunk = next(r.iter_content(65536), b"")
        elapsed = time.time() - started
        r.close()
        if status >= 400:
            return "dead", elapsed, f"HTTP {status}"
        if not chunk:
            return "dead", elapsed, "内容为空"
        size_kb = max(total, len(chunk)) // 1024
        if elapsed > FAST_SECONDS:
            return "slow", elapsed, f"{elapsed:.1f}s, {size_kb}KB"
        return "ok", elapsed, f"{elapsed:.1f}s, {size_kb}KB"
    except Exception as e:  # noqa: BLE001
        return "dead", time.time() - started, type(e).__name__


def probe(url, attempts=3):
    """多次尝试取最好结果。

    raw.githubusercontent.com 在国内时快时慢，单次探测会出现
    "这次 45 秒、下次 0.7 秒"的抖动，据此判死会误杀。重试取最优更接近
    用户实际体验：只要有一次快，通常就能用。
    """
    rank = {"ok": 2, "slow": 1, "dead": -1}   # 初始 best 的 dead 要低于任何真实结果
    best = None
    for i in range(attempts):
        state, secs, note = probe_once(url)
        if best is None or rank[state] > rank[best[0]]:
            best = (state, secs, note)
        if state == "ok":
            break  # 已经拿到好结果，不用再试
        if i < attempts - 1:
            time.sleep(1.5)
    return best or ("dead", 0.0, "未尝试")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="只检查这一个 jar 地址")
    ap.add_argument("--max-slow", type=int, default=0,
                    help="允许几个慢源（默认 0，慢源也视为问题）")
    args = ap.parse_args()

    if args.url:
        state, secs, note = probe(args.url)
        print(f"{state:<5} {note}")
        return 0 if state == "ok" else 1

    rows = []
    for path in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
        name = os.path.basename(path)
        if name in SKIP:
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        spider = data.get("spider")
        if not spider:
            continue
        url = str(spider).split(";")[0]
        sid = name[:-5]
        state, secs, note = probe(url)
        rows.append((sid, state, note, url))
        icon = {"ok": "✅", "slow": "🐢", "dead": "❌"}[state]
        print(f"  {icon} {sid:<16} {note:<16} {url[:62]}")

    ok = [r for r in rows if r[1] == "ok"]
    slow = [r for r in rows if r[1] == "slow"]
    dead = [r for r in rows if r[1] == "dead"]

    print(f"\n可用 {len(ok)} · 慢 {len(slow)} · 不可用 {len(dead)}")
    if slow:
        print("\n慢源（TVBox 加载可能超时）：")
        for sid, _s, note, _u in slow:
            print(f"  {sid:<16} {note}")
    if dead:
        print("\n不可用：")
        for sid, _s, note, _u in dead:
            print(f"  {sid:<16} {note}")

    return 0 if not dead and len(slow) <= args.max_slow else 1


if __name__ == "__main__":
    sys.exit(main())
