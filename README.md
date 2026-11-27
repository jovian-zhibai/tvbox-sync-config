# 影视仓配置聚合仓库（TVBox Config Aggregator）

![配置状态](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjovian-zhibai%2Ftvbox-sync-config%2Fmain%2Foutput%2Fshield.json)
![更新频率](https://img.shields.io/badge/%E6%9B%B4%E6%96%B0-%E6%AF%8F%E5%A4%A9%202%20%E6%AC%A1-blue)

聚合精选的 **20 个**影视仓 / TVBox 配置源（含高天流云、老刘备、yydf、ttkx、小马、王二小等单仓，以及拾光、小盒子、挺好等多仓），通过 **GitHub Actions 定时自动更新**，并把结果直接提交回本仓库，供影视仓、TVBox、OK影视等软件随时拉取最新接口。

**只保留最优 20 个源**：从 600+ 个公开地址里累计探测三轮，按"站点数 + 直播数 + 多仓子源数"综合评分，再做内容去重（同一份配置的不同镜像只留一个），取评分最高的 20 个。当前这 20 个源合计约 1900 个站点、200 个多仓子源，全部实测可用。

### 源的选择规则

**品牌源优先保留** 🏷️ — 肥猫、王二小、老刘备、小马、4K小盒子、小盒子单仓、刺桐娱乐这 7 个是长期维护的知名源，固定占用名额，不参与评分淘汰，`discover.py` 也不会删除它们。

剩余 13 个名额从公开地址里按"站点数 + 直播数×1.5 + 多仓子源数×4"评分补足，并用站点 key 集合去重（同一份配置的不同镜像只留一个）。

> 所有配置均来自互联网公开分享，版权归原作者所有；本仓库仅做聚合与镜像，仅供学习交流，请勿商用。

---

## 一、源可用性状态

<!-- STATUS_START -->
> 🔄 最近更新：2026-11-28 06:26:30（北京时间） · 成功 **20/20** 个源

| 配置源 | 状态 | 使用地址 |
| --- | --- | --- |
| 肥猫 | ✅ 成功 | `https://6296.kstore.vip/facat.json` |
| 王二小 | ✅ 成功 | `https://d.kstore.dev/download/9280/wex.json` |
| 老刘备 | ✅ 成功 | `https://raw.liucn.cc/box/m.json` |
| 小马 | ✅ 成功 | `https://szyyds.cn/tv/x.json` |
| 饭太硬 | ✅ 成功 | `http://www.饭太硬.net/tv` |
| 小盒子单仓 | ✅ 成功 | `http://xhztv.top/xhz` |
| 刺桐娱乐 | ✅ 成功 | `https://www.cttv.vip/ys/json/ctys.json` |
| 高天流云 | ✅ 成功 | `https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json` |
| 拾光多仓 | ✅ 成功 | `http://xmbjm.fh4u.org/dc.txt` |
| 挺好多仓 | ✅ 成功 | `http://ztha.top/TVBox/GYCK.json` |
| 小盒子多仓 | ✅ 成功 | `https://jihulab.com/z-blog/xh2/-/raw/main/t3.json` |
| ttkx | ✅ 成功 | `https://raw.githubusercontent.com/tmoom/ttkx/main/t.json` |
| tmoom xh | ✅ 成功 | `https://raw.githubusercontent.com/tmoom/xh/main/t.json` |
| 小鱼 | ✅ 成功 | `https://6800.kstore.vip/fish.json` |
| jigedos | ✅ 成功 | `https://raw.githubusercontent.com/jigedos/1024/master/jsm.json` |
| jundie | ✅ 成功 | `http://home.jundie.top:81/TVBox/yosakoi.json` |
| 极简单仓 | ✅ 成功 | `https://jihulab.com/tvbox4431737/tvbox/-/raw/main/tv.json` |
| mdxgh | ✅ 成功 | `https://jihulab.com/mdxgh/mdxgh/-/raw/main/md.json` |
| 何诚茶锈 | ✅ 成功 | `https://raw.githubusercontent.com/HeChengChaXiu/tvbox/main/hccx.json` |
| noimank | ✅ 成功 | `https://gitlab.com/noimank/tvbox/-/raw/main/tvbox1.json` |
<!-- STATUS_END -->

## 二、仓库结构

```
tvbox-sync-config/
├── .github/workflows/
│   ├── update.yml                 # 每 12 小时抓取并产出订阅（02:00 / 14:00 UTC）
│   ├── health.yml                 # 每小时探测源健康度，坏源自动下线、恢复自动上线
│   └── discover.yml               # 每周一从公开聚合页发现新源，连续两轮通过才晋升
├── config/
│   ├── sources.json               # 正式源列表（20 个，主地址 + 备用地址）
│   ├── health.json                # 健康检查历史（连续失败/成功次数、最近错误）
│   └── candidates.json            # 候选池（等待连续通过的待晋升源）
├── scripts/
│   ├── update.py                  # 核心更新（下载→校验→合并→落盘→更新状态）
│   ├── health.py                  # 健康检查与自动上下线
│   └── discover.py                # 源发现与自动晋升
├── output/                        # 更新产物（由脚本自动生成并提交）
│   ├── 多仓订阅.json               # 多仓聚合订阅（推荐，App 内可切换各源）
│   ├── 单仓聚合.json               # 单仓聚合（所有源 sites 合并成一个，开箱即用）
│   ├── shield.json                # shields.io 状态徽章数据
│   ├── status.json                # 各源更新状态（机器可读）
│   ├── feimao.json / fantaiying.json / ...  # 各源独立配置
│   └── ...
├── requirements.txt
└── README.md
```

## 三、网页版订阅地址

仓库启用了 GitHub Pages，可以直接在浏览器里查看当前有哪些源、逐个点开复制：

| 入口 | 地址 |
| --- | --- |
| 自定义域名 | <https://tvbox.souljian.cn/> |
| GitHub 默认地址 | <https://jovian-zhibai.github.io/tvbox-sync-config/> |

> 页面本身只做展示，**App 里订阅请用下面 `raw.githubusercontent.com` 的地址** ——
> raw 地址返回纯 JSON，Pages 返回的是网页。

### 自定义域名配置（一次性）

`CNAME` 文件已写好 `tvbox.souljian.cn`，还需在 DNS 服务商（腾讯云 DNSPod）加一条记录：

| 主机记录 | 类型 | 值 |
| --- | --- | --- |
| `tvbox` | CNAME | `jovian-zhibai.github.io` |

> ⚠️ **不要用 `tv.souljian.cn`** —— 那个子域名已被 LibreTV（Vercel）占用。
> 根域 `souljian.cn` 也指向 Vercel，同样不要动。
>
> 如果 GitHub 提示需要验证域名所有权，按提示在 DNS 加一条
> `_github-pages-challenge-jovian-zhibai` 的 TXT 记录即可。

## 四、在影视仓 / TVBox 中使用

部署完成后，把下面任一地址填入 App 的「设置 → 配置地址」：

| 类型 | 地址 | 说明 |
| --- | --- | --- |
| **多仓订阅（推荐）** | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/多仓订阅.json` | App 内可在各源之间切换（20 源全覆盖） |
| **单仓聚合** | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/单仓聚合.json` | 所有源站点合并成一个，无需切换 |
| 单仓 · 肥猫 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/feimao.json` | 3 个地址互为备用 |
| 单仓 · 王二小 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/wangerxiao.json` | 2 个地址互为备用 |
| 单仓 · 老刘备 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/laoliubei.json` | 3 个地址互为备用 |
| 单仓 · 小马 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/xiaoma.json` |  |
| 单仓 · 小盒子单仓 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/xiaohezi.json` |  |
| 单仓 · 刺桐娱乐 🏷️ | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/citong.json` |  |
| 单仓 · 高天流云 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/gao_js.json` | 2 个地址互为备用 |
| 单仓 · yydf 单仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/yydf.json` |  |
| 单仓 · 拾光多仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/shiguang.json` | 2 个地址互为备用 |
| 单仓 · 挺好多仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/tinghao.json` |  |
| 单仓 · 小盒子多仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/xh2_t3.json` |  |
| 单仓 · ttkx | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/ttkx.json` |  |
| 单仓 · tmoom xh | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/tmoom_xh.json` |  |
| 单仓 · 小鱼 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/fish.json` |  |
| 单仓 · 我的九阳影视 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/wdjyys.json` |  |
| 单仓 · 极简单仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/tvbox443.json` |  |
| 单仓 · 萌主影视仓 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/mengzhu_ysc.json` |  |
| 单仓 · mdxgh | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/mdxgh.json` |  |
| 单仓 · 何诚茶锈 | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/hccx.json` |  |
| 单仓 · noimank | `https://raw.githubusercontent.com/jovian-zhibai/tvbox-sync-config/main/output/noimank.json` |  |

> 多仓订阅与单仓文件里的地址由脚本根据 `GITHUB_REPOSITORY` 环境变量自动生成。若国内直连 raw.githubusercontent.com 慢，可套一层 `ghproxy` / `gh-proxy` 等加速前缀。

## 五、自动化机制

三个工作流分工，都用内置 `GITHUB_TOKEN`，不需要任何密钥。它们共用同一把并发锁
（`tvbox-config-write`），避免同时改写 `config/sources.json`。

| 工作流 | 频率 | 作用 |
| --- | --- | --- |
| `update.yml` | 每 12 小时（02:00 / 14:00 UTC，即北京 10:00 / 22:00） | 抓取 20 个源，产出订阅文件，刷新状态表与徽章 |
| `health.yml` | 每小时 | 探测每个源的存活与站点数，连续失败自动下线，恢复后自动上线 |
| `discover.yml` | 每周一 03:00 UTC | 从公开聚合页发现新地址，连续两轮通过才晋升进正式列表 |

### 坏源怎么被自动去掉

`health.py` 每个源的检查结果都会累计：

- 连续失败 **3 次** → `enabled` 置为 `false`，`update.py` 直接跳过它，**用户的多仓订阅里就不会出现这条死链**
- 已下线的源连续成功 **2 次** → 自动恢复上线
- 单仓源站点数少于 **5 个**（或返回空壳）不算健康，防止"能连通但已经半死"的源混进来
- 每次结果写入 `config/health.json` 的 `history`（每个源保留最近 60 条）

### 好源怎么被自动加入

`discover.py` 从几个公开聚合页抓取配置地址，过滤后丢进 `config/candidates.json` 候选池：

- **必须连续 2 轮探测通过**才晋升 —— 一次抽查通过不算，避免抓到临时可用的地址
- 单仓源站点数要 ≥ 20
- **spider 域名白名单校验**：配置里的 `spider` 指向远程 jar 时，域名必须在白名单内（github/gitlab/jihulab/kstore 等）或与配置同域。这条是防投毒的关键 —— 否则别人可以把 `spider` 指向任意 jar，等于往你的播放器里下发可执行代码
- 已有源用过的域名、代理镜像、内容指纹重复的地址都会被剔除
- 源总数受 `max_sources`（20）约束：满了之后只能替换评分更低的自动发现源，**手工维护的源不会被机器人覆盖**

## 六、自定义配置源

编辑 `config/sources.json` 即可增删源或更换地址：

```json
{
  "id": "mysource",
  "name": "我的源",
  "enabled": true,
  "urls": [
    "https://example.com/tv",
    "https://backup.example.com/tv"
  ]
}
```

- `id`：输出文件名（建议英文小写，避免冲突）。
- `name`：在多仓订阅与状态表中展示的名字。
- `enabled`：`false` 时该源被跳过。**这个字段由 `health.py` 自动维护**，一般不用手改。
- `urls`：依次尝试的地址列表，第一个成功的会被使用；建议"主地址在前、备用在后"。

顶层还有两个参数：

- `max_sources`：源数上限（当前 20）。`discover.py` 晋升新源时会遵守它。
- `update_interval_hours`：仅供文档参考，实际频率由 workflow 的 cron 决定。

⚠️ **超出 20 个上限时会发生什么**：`discover.py` 晋升新源前会先删掉评分最低的**自动发现源**（带 `discovered: true` 标记的），腾出位置；如果 20 个全是手工维护的源，它就不晋升，只把新地址留在候选池。所以手工加的源不会被机器人悄悄删掉。

## 七、本地手动更新（可选）

```bash
pip install -r requirements.txt
REPO=jovian-zhibai/tvbox-sync-config python scripts/update.py
```

### 用 sync.sh 同步并推送

本地跑过 `update.py` 后再 `git push`，经常会撞上 Actions 刚提交的产物
（`output/*.json`、README 状态表），产生冲突。这些文件都是同一套脚本
生成的，手工解冲突纯属浪费。`scripts/sync.sh` 把这套流程固化了：

```bash
./scripts/sync.sh            # 拉取 + 解决生成物冲突 + 重新生成 + 推送
./scripts/sync.sh --no-push  # 只同步不推送
./scripts/sync.sh --dry-run  # 只看会做什么，不改任何文件
```

它按文件类型区别对待：

| 冲突文件 | 处理方式 |
| --- | --- |
| `output/*.json`、`README.md` | 自动接受远端版本，随后重跑 `update.py` 重新生成 |
| `config/**`、`scripts/**` 等 | **停下并退出（码 3）**，由你决定 |

配置文件不自动合并是刻意的——`sources.json` 冲突意味着两边改了源列表，
合并错了会直接让订阅出错，这种判断不该交给脚本。

退出码：`0` 正常、`1` 前置检查未通过（有未提交改动 / rebase 未完成）、
`3` 有需人工处理的冲突、`4` 生成失败、`5` 推送失败。

> 脚本内部有个容易踩的坑：`git rebase` 时 `--ours` 指的是**远端**，
> `--theirs` 才是本地提交，与 merge 时相反。代码里显式注释了这点。

## 八、脚本特性

- **中文域名自动转 punycode**：`饭太硬.com` → `xn--sss604efuw.com`，避免 DNS 解析失败。
- **多地址回退**：每个源按顺序尝试主/备用地址，单个地址失败不影响其他源。
- **智能重试**：仅对超时、连接错误、空响应等瞬态问题退避重试；4xx/5xx 等确定性失败直接跳过。
- **兼容多仓订阅**：既支持单仓（含 sites 字段），也支持多仓订阅（顶层 urls 数组）格式。
- **反爬兼容**：使用简洁 UA（部分接口对完整浏览器 UA 下发挑战页），自动剔除 JSON 内嵌的 `//` 注释，兼容未转义控制字符。
- **聚合单仓**：把所有成功源的 `sites` 按 key 去重合并（重复 key 自动加源前缀），`lives/parses` 等列表合并去重。
- **状态可视化**：每次更新自动刷新 README 状态表与 shields.io 徽章。
- **部分成功可用**：只要有一个源成功就产出可用订阅，失败源记录在 `status.json` 与 README 状态表。

## 九、常见问题

**某个源一直失败？**
大部分源做了地区/频率限制，GitHub Actions 和本地网络环境不同，可能一边能访问、另一边不行。脚本会按 `urls` 顺序自动尝试所有备用地址，只把成功的写进去；连续失败 3 次后 `health.py` 会自动把它下线。

**自动提交会不会死循环？**
不会。`update.yml` 的 push 触发只监听 `config/`、`scripts/`、`requirements.txt`，而它自己只改 `output/` 和 README 状态区，不会自我触发。

**不会自我触发，但会主动补跑。** GitHub 有一条防递归规则：用内置 `GITHUB_TOKEN` 做的提交**不会**触发其它 workflow。所以 `health.yml` 和 `discover.yml` 改完 `config/sources.json` 后，`update.yml` 并不会被 push 触发 —— 它们会在同一个 job 里显式跑一次 `python scripts/update.py` 并提交产物。

三个工作流共用 `concurrency: tvbox-config-write`，同一时刻只跑一个，不会互相覆盖。

**为什么只有 20 个源？**
源不是越多越好。每多一个源就多一份失效风险和一次请求开销，而 TVBox 里真正被使用的通常只有前几个。20 个已经覆盖约 1900 个站点。

淘汰的源没有丢，都在 `config/reserve.json` 里（19 个，含饭太硬、讴歌这两个暂时失效的品牌源）。想换回某个源时，把它整项复制到 `config/sources.json` 即可。

**想加自己的源？**
在 `config/sources.json` 里加一项即可，但注意总数上限是 20 —— 超出时 `discover.py` 只会淘汰机器人自己加的源，你手写的不会被删。

## 十、免责声明

本项目仅用于学习、测试与个人使用；聚合的接口资源来自互联网公开分享，版权归原作者所有。若涉及侵权，请联系删除相应内容。
