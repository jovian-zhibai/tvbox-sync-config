#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置源自动发现
==============
从公开聚合页里抓取 TVBox 配置地址，去重后放进候选池 config/candidates.json，
并对候选做多轮探测。连续 PROMOTE_ROUNDS 轮通过且站点数达标的候选，
自动晋升进 config/sources.json。

安全约束（重要）：
  1. 只接受 http/https，拒绝内网/回环地址
  2. 已有源用过的域名直接跳过（避免重复）
  3. 站点数必须 ≥ MIN_SITES，防止把空壳塞进正式列表
  4. spider 域名必须在 ALLOWED_SPIDER_HOSTS 里，或与配置自身同域
     —— 这条是防投毒的关键：别人可以把 spider 指向任意 jar，
     等于往用户播放器里下发可执行代码
  5. 每轮结果写进候选的 history，晋升需要"连续 N 轮"而不是"一次抽查"

用法：
  python scripts/discover.py                # 抓取 + 探测 + 写候选池 + 自动晋升
  python scripts/discover.py --no-promote   # 只更新候选池，不碰正式列表
"""
import argparse
import concurrent.futures as cf
import datetime
import ipaddress
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "config", "sources.json")
CAND_FILE = os.path.join(ROOT, "config", "candidates.json")

# —— 探测与晋升阈值 ——
PROMOTE_ROUNDS = 2      # 连续几轮通过才晋升
MIN_SITES = 20          # 单仓源最少站点数
MAX_CANDIDATES = 200    # 候选池上限，超出按得分淘汰
TIMEOUT = 10

TZ = datetime.timezone(datetime.timedelta(hours=8))

# 可以抓取的公开聚合页。失效的页面不会让脚本失败，只是那一页没收获。
DISCOVERY_PAGES = [
    "https://m.7po.com/article/3175.html",
    "https://m.7po.com/article/2189.html",
    "https://www.159e.cn/1838.html",
    "https://www.wxyz.tw/wxyz_tw_lib/18519.html",
]

# 允许作为 spider 的域名后缀。命中这里或与配置同域的 jar 才放行。
ALLOWED_SPIDER_HOSTS = (
    "github.com", "githubusercontent.com", "gitlab.com", "jihulab.com",
    "gitee.com", "jsdelivr.net", "ghproxy.net", "gh-proxy.com",
    "kstore.vip", "kstore.dev", "kstore.space", "kstore.work",
)

# 明显不是配置地址的路径/关键字
SKIP_PATTERNS = (
    "pan.quark", "pan.baidu", "gg.gg", "t.cn", "/article/", "/apps/",
    ".apk", ".dmg", ".exe", ".zip", ".png", ".jpg", ".jpeg", ".gif",
    ".css", ".html", ".htm", "play.google", "apps.apple",
)

URL_RE = re.compile(r"https?://[a-zA-Z0-9._%/?=&:@~+\-\u4e00-\u9fff]+")


# ---------------------------------------------------------------- 工具

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] 读取 {path} 失败：{e}", file=sys.stderr)
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_public_url(url):
    """拒绝内网、回环、非 http(s)。"""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = p.hostname
    if not host:
        return False
    if host in ("localhost", "0.0.0.0", "::1"):
        return False
    # 纯 IP 时判断是否私有段
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass  # 域名，继续
    return True


def host_of(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_spider_allowed(spider, source_url):
    """校验 spider（远程 jar / txt）是否来自可信域或与配置同域。"""
    if not spider:
        return True
    s = str(spider)
    # 本地相对路径（./jar/x.jar）由配置自身提供，不算远程下发
    if not s.startswith(("http://", "https://")):
        return True
    sh = host_of(s)
    if not sh:
        return False
    if sh == host_of(source_url):
        return True
    return any(sh == h or sh.endswith("." + h) for h in ALLOWED_SPIDER_HOSTS)


# ---------------------------------------------------------------- 抓取页面

def fetch_page(url):
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                         timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 页面抓取失败 {url}: {str(e)[:80]}", file=sys.stderr)
        return ""


def extract_urls(text):
    out = set()
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;:)】]}>\"'")
        low = u.lower()
        if any(p in low for p in SKIP_PATTERNS):
            continue
        if not is_public_url(u):
            continue
        out.add(u)
    return out


# ---------------------------------------------------------------- 探测

def probe_candidate(url):
    """返回 (ok, detail)。比 health.py 更严，因为这是新源入场。"""
    try:
        data = update.fetch_config(url)
    except Exception as e:  # noqa: BLE001
        return False, {"error": str(e)[:160]}

    sites = data.get("sites") or []
    children = data.get("urls") or []
    n_sites = len(sites) if isinstance(sites, list) else 0
    n_children = len(children) if isinstance(children, list) else 0

    if not n_children and n_sites < MIN_SITES:
        return False, {"error": f"站点数不足（{n_sites} < {MIN_SITES}）"}

    spider = data.get("spider")
    if not is_spider_allowed(spider, url):
        return False, {"error": f"spider 域名不可信：{str(spider)[:60]}"}

    return True, {
        "kind": "multi" if n_children else "single",
        "sites": n_sites,
        "lives": len(data.get("lives") or []) if isinstance(data.get("lives"), list) else 0,
        "children": n_children,
        "spider": str(spider)[:120] if spider else None,
    }


# ---------------------------------------------------------------- 主流程

def canonical_target(url):
    """还原代理前缀，得到配置的真实地址。

    ghproxy.net/https://raw.githubusercontent.com/x/y.json
    与 raw.githubusercontent.com/x/y.json 是同一份配置，
    不归一化就会把同一个源当成两个新源重复收录。
    """
    u = url
    for _ in range(3):  # 允许套娃代理
        m = re.match(r"^https?://[^/]+/(https?://.+)$", u)
        if not m:
            break
        u = m.group(1)
    return u.rstrip("/").lower()


def config_fingerprint(detail):
    """内容指纹：同站点数/直播数/子仓数视为同一份配置。"""
    return (detail.get("kind"), detail.get("sites"),
            detail.get("lives"), detail.get("children"))


def make_id(url, taken):
    """由域名+路径生成 id。冲突时加序号。"""
    h = host_of(url) or "src"
    base = re.sub(r"[^a-z0-9]+", "_", h).strip("_")
    base = base.split(".")[0] or "src"
    # 代理地址的 host 是代理本身，用真实目标的主机名更有意义
    target_host = host_of(canonical_target(url))
    if target_host:
        tb = re.sub(r"[^a-z0-9]+", "_", target_host).strip("_").split(".")[0]
        if tb and tb not in base:
            base = f"{base}_{tb}"
    sid = base
    i = 2
    while sid in taken:
        sid = f"{base}{i}"
        i += 1
    taken.add(sid)
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-promote", action="store_true", help="只更新候选池，不晋升")
    args = ap.parse_args()

    cfg = load_json(CONFIG_FILE, {"sources": []})
    cand_doc = load_json(CAND_FILE, {"candidates": {}, "updated_at": None})
    candidates = cand_doc.setdefault("candidates", {})

    sources = cfg.get("sources", [])
    known_urls = {u for s in sources for u in s.get("urls", [])}
    known_hosts = {host_of(u) for u in known_urls}

    print(f"已有 {len(sources)} 个源，{len(known_urls)} 个地址\n")

    # —— 1. 抓页面 ——
    found = set()
    for page in DISCOVERY_PAGES:
        html = fetch_page(page)
        if not html:
            continue
        got = extract_urls(html)
        print(f"  页面 {page} → {len(got)} 个候选")
        found |= got

    # —— 2. 过滤 ——
    known_canonical = {canonical_target(u) for u in known_urls}
    known_prints = set()
    fresh = []
    seen_canonical = set()
    for u in sorted(found):
        if u in known_urls:
            continue
        if canonical_target(u) in known_canonical:
            continue  # 同一份配置的代理镜像
        if host_of(u) in known_hosts and not re.match(r"^https?://[^/]+/https?://", u):
            continue  # 同域直连，多半是同一份配置
        if u in candidates:
            continue
        canon = canonical_target(u)
        if canon in seen_canonical:
            continue  # 本轮内多个代理指向同一目标，只留一个
        seen_canonical.add(canon)
        fresh.append(u)
    print(f"\n新候选 {len(fresh)} 个（已去重已知源，待探测）\n")

    # —— 3. 并发探测新候选 ——
    now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    fresh_passed = {}
    if fresh:
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(probe_candidate, u): u for u in fresh}
            for fut in cf.as_completed(futs):
                u = futs[fut]
                try:
                    ok, detail = fut.result()
                except Exception as e:  # noqa: BLE001
                    ok, detail = False, {"error": f"探测异常：{e}"}
                if ok:
                    fresh_passed[u] = detail
                    print(f"  OK   sites={detail['sites']:<4} lives={detail['lives']:<3} "
                          f"ch={detail['children']:<3} {u}")
                else:
                    print(f"  --   {u}  {detail.get('error','')[:60]}")

    # 本轮新发现的追加到候选池，计 1 次通过。
    # 注意：这些不参与下面的"复检"，否则同一轮会被算两次，
    # 跨轮稳定性校验就失效了。
    # 同时按内容指纹去重：同一份配置换了域名/代理，不应重复收录。
    existing_prints = {config_fingerprint(c) for c in candidates.values()
                       if c.get("sites") or c.get("children")}
    for u, detail in fresh_passed.items():
        fp = config_fingerprint(detail)
        if fp in existing_prints:
            print(f"  (跳过内容重复) {u}")
            continue
        existing_prints.add(fp)
        candidates[u] = {
            "url": u,
            "first_seen": now,
            "consecutive_passes": 1,
            "last_check_at": now,
            **detail,
        }

    # —— 4. 复检"上一轮之前"就在池里的候选 ——
    existing = {u: c for u, c in candidates.items() if u not in fresh_passed}
    if existing:
        print(f"\n复检 {len(existing)} 个已有候选…")
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(probe_candidate, u): u for u, c in existing.items()}
            for fut in cf.as_completed(futs):
                u = futs[fut]
                c = candidates[u]
                try:
                    ok, detail = fut.result()
                except Exception:  # noqa: BLE001
                    ok, detail = False, {"error": "探测异常"}
                c["last_check_at"] = now
                if ok:
                    c["consecutive_passes"] = c.get("consecutive_passes", 0) + 1
                    c.pop("last_error", None)
                    for k in ("kind", "sites", "lives", "children", "spider"):
                        if k in detail:
                            c[k] = detail[k]
                else:
                    c["consecutive_passes"] = 0
                    c["last_error"] = detail.get("error")

    # —— 6. 晋升 ——
    promoted = []
    if not args.no_promote:
        max_sources = int(cfg.get("max_sources", 0) or 0)
        taken_ids = {s.get("id") for s in sources}
        enabled_count = sum(1 for s in sources if s.get("enabled", True))

        # 源数上限：满了之后先淘汰评分最低的"自动发现"源，再考虑晋升。
        # 手工维护的源不动 —— 那是人的判断，机器人不该覆盖。
        for u, c in sorted(candidates.items(),
                           key=lambda kv: -kv[1].get("consecutive_passes", 0)):
            if c.get("consecutive_passes", 0) < PROMOTE_ROUNDS:
                continue
            if c.get("sites", 0) < MIN_SITES and not c.get("children"):
                continue

            if max_sources and enabled_count >= max_sources:
                auto = [s for s in sources if s.get("discovered") and s.get("enabled", True)]
                if not auto:
                    print(f"  源数已达上限 {max_sources}，且没有可替换的自动源，停止晋升")
                    break
                weakest = min(auto, key=lambda s: s.get("score", 0))
                new_score = c.get("sites", 0) + c.get("lives", 0) * 1.5 + c.get("children", 0) * 4.0
                if new_score <= weakest.get("score", 0):
                    continue  # 新源还不如现有的，不换
                sources.remove(weakest)
                taken_ids.discard(weakest.get("id"))
                enabled_count -= 1
                print(f"  替换最弱的自动源 {weakest.get('id')}（评分 {weakest.get('score')}）")

            sid = make_id(u, taken_ids)
            label = "多仓" if c.get("kind") == "multi" else "单仓"
            sources.append({
                "id": sid,
                "name": f"自动发现·{host_of(u).split('.')[0]}（{label}）",
                "enabled": True,
                "discovered": True,
                "discovered_at": now,
                "score": round(c.get("sites", 0) + c.get("lives", 0) * 1.5
                               + c.get("children", 0) * 4.0, 1),
                "urls": [u],
            })
            promoted.append((sid, u, c.get("sites"), c.get("children")))
            enabled_count += 1
            del candidates[u]

    # —— 7. 候选池上限 ——
    if len(candidates) > MAX_CANDIDATES:
        keep = sorted(candidates.items(),
                      key=lambda kv: (kv[1].get("consecutive_passes", 0),
                                      kv[1].get("sites", 0)),
                      reverse=True)[:MAX_CANDIDATES]
        candidates.clear()
        candidates.update(dict(keep))
        print(f"候选池超出上限，保留得分最高的 {MAX_CANDIDATES} 个")

    cfg["sources"] = sources
    cand_doc["updated_at"] = now
    save_json(CONFIG_FILE, cfg)
    save_json(CAND_FILE, cand_doc)

    print("\n" + "=" * 50)
    print(f"候选池：{len(candidates)} 个（通过一轮及以上）")
    if promoted:
        print(f"自动晋升 {len(promoted)} 个新源：")
        for sid, u, sites, ch in promoted:
            print(f"  + {sid:<16} sites={sites:<4} ch={ch:<3} {u}")
    else:
        print("本轮无新源晋升（需连续 "
              f"{PROMOTE_ROUNDS} 轮通过）。")
    print(f"正式源总数：{len(sources)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
