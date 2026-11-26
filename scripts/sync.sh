#!/bin/bash
# 同步远端并推送，自动处理"生成物冲突"。
#
# 背景：仓库里有两类文件会同时被两边改动
#   1. 生成物  output/*.json、README.md 的状态表 —— Actions 每 12 小时
#      自动提交一次，本地跑 update.py 也会重写，内容都由同一套脚本产出
#   2. 配置    config/sources.json 等 —— 只由人或脚本显式修改
#
# 生成物冲突时不该手工编辑：正确做法是接受任意一方，然后重跑 update.py
# 重新生成，结果必然一致。配置文件冲突则必须人工确认，脚本会停下。
#
# 注意 git rebase 的语义陷阱：
#   --ours   = 上游（远端）的内容
#   --theirs = 你正在 rebase 的那个提交（本地）
# 与 merge 时相反，所以这里显式写清楚，不靠直觉。
#
# 用法：
#   ./scripts/sync.sh            # 拉取 + 解决生成物冲突 + 推送
#   ./scripts/sync.sh --no-push  # 只同步不推送
#   ./scripts/sync.sh --dry-run  # 只看会做什么

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

BRANCH="main"
PUSH=1
DRY=0
for arg in "$@"; do
  case "$arg" in
    --no-push) PUSH=0 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

# 会被脚本自动重写、冲突可安全丢弃的文件
is_generated() {
  case "$1" in
    output/*.json) return 0 ;;
    README.md)     return 0 ;;
    *)             return 1 ;;
  esac
}

say() { printf '%s\n' "$*"; }
run() { if [ "$DRY" = "1" ]; then say "  [dry] $*"; else "$@"; fi; }

# ---------------------------------------------------------------- 前置检查
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  say "⚠️  检测到未完成的 rebase。"
  say "    先处理：git rebase --abort   或   ./scripts/sync.sh --continue"
  exit 1
fi

if [ -n "$(git status --porcelain | grep -v '^??' || true)" ]; then
  say "⚠️  工作区有未提交改动，先提交或 stash："
  git status --short | head -20
  exit 1
fi

say "==> 拉取 origin/$BRANCH"
if [ "$DRY" = "1" ]; then
  say "  [dry] git fetch origin $BRANCH && git rebase origin/$BRANCH"
else
  git fetch --quiet origin "$BRANCH" || { say "拉取失败"; exit 1; }
fi

BEHIND=$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)
say "    远端领先 $BEHIND 个提交"

# ---------------------------------------------------------------- rebase
resolve_conflicts() {
  local unresolved
  unresolved=$(git diff --name-only --diff-filter=U)
  [ -z "$unresolved" ] && return 0

  local generated=() config=()
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_generated "$f"; then generated+=("$f"); else config+=("$f"); fi
  done <<< "$unresolved"

  if [ ${#config[@]} -gt 0 ]; then
    # 生成物仍然顺手解决掉，这样人工只需处理真正需要判断的那几个文件
    if [ ${#generated[@]} -gt 0 ]; then
      say "    生成物冲突 ${#generated[@]} 个，先自动采用远端版本："
      for f in "${generated[@]}"; do
        say "      · $f"
        run git checkout --ours -- "$f"
        run git add -- "$f"
      done
    fi
    say ""
    say "❌ 非生成物冲突，需要人工判断："
    for f in "${config[@]}"; do say "     $f"; done
    say ""
    say "   生成物（output/*.json、README.md）已自动处理，"
    say "   但这些文件涉及实际配置，不替你决定。"
    say "   处理完后执行： git rebase --continue"
    say "   然后重新运行： ./scripts/sync.sh"
    return 1
  fi

  say "    生成物冲突 ${#generated[@]} 个，自动采用远端版本后重新生成："
  for f in "${generated[@]}"; do
    say "      · $f"
    # --ours 在 rebase 中 = 远端。取谁都不影响，稍后统一重跑生成。
    run git checkout --ours -- "$f"
    run git add -- "$f"
  done
  return 0
}

if [ "$BEHIND" != "0" ] || [ "$DRY" = "1" ]; then
  say "==> rebase 到 origin/$BRANCH"
  if [ "$DRY" = "1" ]; then
    say "  [dry] git rebase origin/$BRANCH"
  else
    if ! git rebase "origin/$BRANCH" >/tmp/sync_rebase.log 2>&1; then
      if ! resolve_conflicts; then
        say ""
        say "rebase 未完成，日志：/tmp/sync_rebase.log"
        exit 3
      fi
      say "==> 继续 rebase"
      if ! GIT_EDITOR=true git rebase --continue >>/tmp/sync_rebase.log 2>&1; then
        # 连续冲突：再试一轮
        if ! resolve_conflicts; then
          say "rebase 仍冲突，日志：/tmp/sync_rebase.log"; exit 3
        fi
        GIT_EDITOR=true git rebase --continue >>/tmp/sync_rebase.log 2>&1 || {
          say "rebase 失败，日志：/tmp/sync_rebase.log"; exit 3
        }
      fi
    fi
  fi
else
  say "    已是最新，无需 rebase"
fi

# ---------------------------------------------------------------- 重新生成
# 生成物冲突时取的是远端版本，必须用本地脚本重算一遍保证一致
say "==> 重新生成订阅产物"
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import requests" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  VER="$(ls -d /tmp/.tvbenv/bin/python 2>/dev/null || true)"
  [ -n "$VER" ] && PY="$VER"
fi

if [ -z "$PY" ]; then
  say "⚠️  找不到带 requests 的 Python，跳过重新生成。"
  say "    安装： pip install -r requirements.txt"
else
  say "    使用 $PY"
  if [ "$DRY" = "1" ]; then
    say "  [dry] env REPO=jovian-zhibai/tvbox-sync-config $PY scripts/update.py"
  else
    if ! env REPO=jovian-zhibai/tvbox-sync-config "$PY" scripts/update.py >/tmp/sync_update.log 2>&1; then
      say "update.py 失败，日志：/tmp/sync_update.log"
      tail -5 /tmp/sync_update.log | sed 's/^/      /'
      exit 4
    fi
  fi
  if [ "$DRY" = "0" ]; then
    if [ -n "$(git status --porcelain output README.md)" ]; then
      say "    产物有变化，提交"
      run git add output README.md
      run git commit -q -m "chore: 重新生成订阅产物 $(date -u +'%Y-%m-%d %H:%M UTC')"
    else
      say "    产物无变化"
    fi
  fi
fi

# ---------------------------------------------------------------- 推送
if [ "$PUSH" = "1" ]; then
  if [ "$DRY" = "1" ]; then
    say "  [dry] git push origin $BRANCH"
  else
    AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD")
    if [ "$AHEAD" = "0" ]; then
      say "==> 没有需要推送的提交"
    else
      say "==> 推送 $AHEAD 个提交"
      git push origin "$BRANCH" || { say "推送失败"; exit 5; }
    fi
  fi
fi

say ""
say "✅ 同步完成"
