#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置源健康检查
==============
对 config/sources.json 里的每个源做真实抓取与结构校验，并把结果累计到
config/health.json。规则：

  - 连续 FAIL_THRESHOLD 次检查失败 → 该源 enabled 置为 false（自动下线）
  - 已下线的源连续 RECOVER_THRESHOLD 次通过 → enabled 置回 true（自动上线）
  - 每次结果都写进 history，最多保留 HISTORY_KEEP 条，便于回溯

只改配置，不抓内容落盘 —— 真正产出订阅还是 update.py 的活。
坏源下线后 update.py 会跳过它，用户拿到的多仓订阅里就不会出现死链。

用法：
  python scripts/health.py            # 检查并更新 config/
  python scripts/health.py --dry-run  # 只报告，不写文件
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update  # noqa: E402  复用完全相同的抓取/校验逻辑

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "config", "sources.json")
HEALTH_FILE = os.path.join(ROOT, "config", "health.json")

FAIL_THRESHOLD = 3      # 连续失败几次下线
RECOVER_THRESHOLD = 2   # 连续成功几次上线
HISTORY_KEEP = 60       # 每个源保留多少条历史
MIN_SITES = 5           # 单仓源站点数低于此值视为异常（防返回空壳）

TZ = datetime.timezone(datetime.timedelta(hours=8))


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] 无法读取 {path}：{e}，使用默认值", file=sys.stderr)
        return default


def probe(url):
    """返回 (ok, 详情)。复用 update.fetch_config，保证和正式流程判定一致。"""
    try:
        data = update.fetch_config(url)
    except Exception as e:  # noqa: BLE001
        return False, {"error": str(e)[:200]}

    sites = data.get("sites") or []
    lives = data.get("lives") or []
    children = data.get("urls") or []
    count = len(sites) if isinstance(sites, list) else 0

    # 空壳检测：单仓源站点太少说明源已经半死，不能算健康
    if not children and count < MIN_SITES:
        return False, {"error": f"站点数过少（{count} < {MIN_SITES}），疑似空壳"}

    return True, {
        "kind": "multi" if children else "single",
        "sites": count,
        "lives": len(lives) if isinstance(lives, list) else 0,
        "children": len(children) if isinstance(children, list) else 0,
    }


def check_source(src):
    """按顺序尝试主/备地址，任一成功即视为健康。"""
    last_detail = {"error": "没有配置任何地址"}
    urls = src.get("urls", [])
    for url in urls:
        ok, detail = probe(url)
        if ok:
            detail["url"] = url
            return ok, detail
        detail["url"] = url
        last_detail = detail
    return False, last_detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写回配置")
    args = ap.parse_args()

    cfg = load_json(CONFIG_FILE, {"sources": []})
    health = load_json(HEALTH_FILE, {"sources": {}, "updated_at": None})
    sources = cfg.get("sources", [])
    if not sources:
        print("没有配置源，退出。")
        return 0

    print(f"检查 {len(sources)} 个源…\n")
    results = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(check_source, s): s for s in sources}
        for fut in cf.as_completed(futures):
            src = futures[fut]
            sid = src.get("id")
            try:
                ok, detail = fut.result()
            except Exception as e:  # noqa: BLE001
                ok, detail = False, {"error": f"检查异常：{e}"}
            results[sid] = (ok, detail)
            flag = "OK  " if ok else "FAIL"
            if ok:
                print(f"  {flag} {src.get('name', sid):<16} sites={detail.get('sites', 0):<4} "
                      f"lives={detail.get('lives', 0):<3} {detail.get('url')}")
            else:
                print(f"  {flag} {src.get('name', sid):<16} {detail.get('error', '')[:70]}")

    now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    changed = []
    max_sources = int(cfg.get("max_sources", 0) or 0)

    for src in sources:
        sid = src.get("id")
        ok, detail = results.get(sid, (False, {"error": "未检查"}))
        entry = health["sources"].setdefault(sid, {
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "history": [],
        })

        if ok:
            entry["consecutive_failures"] = 0
            entry["consecutive_successes"] = entry.get("consecutive_successes", 0) + 1
            entry["last_ok_at"] = now
            entry["last_error"] = None
        else:
            entry["consecutive_successes"] = 0
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            entry["last_fail_at"] = now
            entry["last_error"] = detail.get("error")

        entry["last_url"] = detail.get("url")
        entry["last_check_at"] = now
        entry["last_sites"] = detail.get("sites")
        entry.setdefault("history", []).append(
            {"at": now, "ok": ok, "sites": detail.get("sites"), "error": detail.get("error")}
        )
        entry["history"] = entry["history"][-HISTORY_KEEP:]

        # —— 下线 / 上线判定 ——
        was_enabled = src.get("enabled", True)
        if was_enabled and entry["consecutive_failures"] >= FAIL_THRESHOLD:
            src["enabled"] = False
            entry["disabled_at"] = now
            changed.append(f"⛔ 下线 {src.get('name', sid)}（连续失败 {entry['consecutive_failures']} 次）")
        elif not was_enabled and entry["consecutive_successes"] >= RECOVER_THRESHOLD:
            src["enabled"] = True
            entry.pop("disabled_at", None)
            changed.append(f"✅ 恢复 {src.get('name', sid)}（连续成功 {entry['consecutive_successes']} 次）")

    ok_count = sum(1 for ok, _ in results.values() if ok)
    enabled_count = sum(1 for s in sources if s.get("enabled", True))
    health["updated_at"] = now
    health["summary"] = {
        "total": len(sources),
        "healthy": ok_count,
        "degraded": len(sources) - ok_count,
        "enabled": enabled_count,
        "max_sources": max_sources or None,
    }

    print(f"\n健康 {ok_count}/{len(sources)}")
    if max_sources and enabled_count > max_sources:
        print(f"⚠️ 启用源 {enabled_count} 个，超过上限 {max_sources}，"
              f"请检查 config/sources.json")
    if changed:
        print("\n配置变更：")
        for c in changed:
            print("  " + c)
    else:
        print("\n配置无变更。")

    if args.dry_run:
        print("\n--dry-run：未写入文件。")
        return 0

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n已写入 {CONFIG_FILE} / {HEALTH_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
