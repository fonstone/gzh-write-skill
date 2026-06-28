# GzhWrite

微信公众号内容全流程 AI Skill —— 从热点抓取到草稿箱推送，一句话搞定。

兼容 [OpenCode](https://github.com/anomalyco/opencode)、[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 和 [OpenClaw](https://github.com/anthropics/openclaw) 的 skill 格式。安装后说「写一篇公众号文章」即可触发完整流程。

## 它能做什么

```
"写一篇公众号文章"
  → 抓热点 → 选题评分 → 标题三件套拟题 → 框架选择（五段式骨架）
  → 素材采集（webfetch 真实数据）→ 内容增强（4 高分动作）
  → 写作（开头三法 + 视角切换 micro↔macro + 真实信息锚定 + 风格注入 + 编辑锚点）
  → SEO优化（标题钩子 + CTA三要素）→ AI配图 → 微信排版 → 推送草稿箱
```

首次使用时会引导你设置公众号风格，之后每次只需一句话。生成的文章带有 2-3 个编辑锚点——花 3-5 分钟加入你自己的话，文章就会从"AI 初稿"变成"你的作品"。

## 核心能力

| 能力 | 说明 | 实现 |
|------|------|------|
| 热点抓取 | 微博 + 头条 + 百度实时热搜 | `scripts/fetch_hotspots.py` |
| SEO 评分 | 百度 + 360 搜索量化评分 | `scripts/seo_keywords.py` |
| 选题生成 | 10 选题 × 3 维度评分 + 历史去重 + 三类标题钩子 | `references/topic-selection.md` |
| 素材采集 | `webfetch` 抓取真实数据/引述/案例 | SKILL.md Step 3.2 |
| 框架生成 | 通用五段式骨架 + 7 套变体框架（痛点/故事/清单/对比/热点解读/纯观点/复盘） | `references/frameworks.md` |
| 内容增强 | 4 策略（角度发现/密度强化/细节锚定/真实体感）+ 4 共性高分动作（人话转译/横向对比/技术商业双视角/信息密度节奏） | `references/content-enhance.md` |
| 文章写作 | 五段式骨架 + 开头三法 + 视角切换 micro↔macro + 真实信息锚定 + 风格注入 + 编辑锚点 + 五条 AI 味戒律 | `references/writing-guide.md` |
| 标题优化 | 三类可复用钩子：时效数据前置 / 精准人群锚定 / 学术权威承诺 | `references/seo-rules.md` |
| 结尾收束 | 金句 + CTA 三件套（紧迫感 + 低门槛 + 价值可视化） | `references/seo-rules.md` |
| 视觉 AI | 封面 3 创意 + 内文 3-6 配图（架构图/对比表/实测截图优先） | `toolkit/image_gen.py` |
| 排版发布 | 16 主题 + 微信兼容修复 + 暗黑模式 | `toolkit/cli.py` |
| 效果复盘 | 微信数据分析 API 回填阅读数据 | `references/effect-review.md` |
| 范文风格库 | SICO 式 few-shot：从你的文章提取风格指纹，写作时注入 | `scripts/extract_exemplar.py` |
| 风格飞轮 | 学习你的修改，越用越像你 | `references/learn-edits.md` |
| 排版学习 | 从任意公众号文章 URL 提取排版主题 | `scripts/learn_theme.py` |
| 文章采集 | 从公众号 URL 提取正文为 Markdown，可导入范文库 | `scripts/fetch_article.py` |

## 标题三件套

标题是打开率的决定性因素。本 Skill 在 `seo-rules.md` 拆出三类可复用钩子，每个有技法公式 + 好差例 + 反常识点：

| 钩子 | 技法公式 | 适用派别 |
|------|----------|---------|
| 时效+数据前置 | `[时间戳]+[事件]+[量化冲击变量]` | 资讯派 |
| 精准人群锚定+反常识+强结果 | `[行为标签]+[反常识]+[替代行为/强结果]` | 工具/人格派 |
| 学术权威+价值承诺 | `[权威来源]+[话题]+[收益承诺词]` | 技术派 |

关键：泛标签（"AI 从业者必看"）已死，行为标签（"天天加班到 10 点的打工人"）当立。

## 五段式骨架

所有框架共享的底层骨架，按功能和字数占位：

| 段 | 功能 | 占比 | 字数 | 纪律 |
|----|------|------|------|------|
| 一 | 场景钩子 | 10% | ≈200 | 三选一钩法，行为标签锁人 |
| 二 | 背景/机制拆解 | 25% | ≈500-700 | 派别分支，段落≤3行 |
| 三 | 核心干货 | 45% | ≈900-1300 | 测评/趋势/实操三变体，干度要够 |
| 四 | 延伸/冲突 | 15% | ≈300-400 | 拉开和营销号的差距 |
| 五 | 金句+CTA | 5% | ≈100 | 1 句截图话 + CTA 三件套 |

## 写作人格

像选排版主题一样选写作风格。在 `style.yaml` 里一行配置：

```yaml
writing_persona: "ai-cultivator"
opening_hook: "U"        # U=按人格默认；或显式指定 problem_hook/data_punch/scene 等
cta_strict: true         # 结尾是否强制 CTA 三件套
```

| 人格 | 适合 | 默认钩子 | 视角切换 (micro ↔ macro) |
|------|------|---------|---------------------------|
| `ai-cultivator` | AI技术深度号/工程师博客 | problem_hook | 技术实测细节 ↔ 工程产业实践 |
| `midnight-friend` | 个人号/自媒体 | personal_moment | 个人经历细节 ↔ 时代结构共性 |
| `warm-editor` | 生活/文化/情感 | scene | 感官细节 ↔ 普遍性处境 |
| `industry-observer` | 行业媒体/分析 | news_hook | 企业事件 ↔ 资本流向/格局 |
| `sharp-journalist` | 新闻/评论 | cold_open | 个案事实 ↔ 权力格局 |
| `cold-analyst` | 财经/投研 | data_punch | 季度财务 ↔ 跨周期规律 |

每个人格定义了：语气浓度、数据呈现方式、情绪弧线、不确定性表达模板、开头三法候选、结尾金句+CTA 默认形式、显微镜↔望远镜切换节奏、AI 味雷区避免列表。详见 `personas/` 目录。

## 内容质量

GzhWrite 的目标不是"骗过 AI 检测"，而是**写出值得读的文章**。核心机制：

1. **内容增强**：根据框架类型自动执行不同策略——热点文找反直觉角度、干货文强化信息密度、故事文锚定真实细节、对比文注入真实用户体感
2. **四个共性高分动作**（跨派通用）：人话转译、横向对比、技术商业双视角、信息密度节奏
3. **素材采集**：自动抓取真实数据/引述/案例，锚定在文章中（不编造）
4. **范文风格库**：导入你已发布的文章，写作时自动注入你的风格指纹（句长节奏、情绪表达、转折方式）
5. **视角切换**：每个干货段后跟一个把它放大到 macro 视角的判断——纯微观是论文博客，纯宏观是行业报告，头部号都在中间那条线
6. **编辑锚点**：在 2-3 个关键位置标记"在这里加一句你自己的话"
7. **学习飞轮**：每次你编辑后说"学习我的修改"，下次初稿更接近你的风格
8. **文章自检**：说"检查一下"，查看生成档案（用了什么框架/人格/策略）+ 质量检查（具体到哪句话该怎么改）

## 五条 AI 味戒律

写完后扫一遍，命中一条改一条：

| 戒律 | 触发词 / 表现 | 怎么改 |
|------|--------------|--------|
| 1. 综上式收束 | "综上所述""值得注意的是""不难发现""由此可见" | 直接删 |
| 2. AI 互联网黑话 | 赋能、闭环、对齐、抓手、链路、聚焦 | 改大白话 |
| 3. 堆术语不转译 | 一段三个英文术语不带类比 | 每个术语配日常类比 |
| 4. 无观点只搬运 | "X 发布了 Y，引起关注" 后面没判断 | 加一句"我怎么看" |
| 5. 排版密不透风 | 3 段以上不换行、200 字以上无小标题 | 拆段 + 加 H2 + 加粗 |

详见 `references/writing-guide.md`。

## 排版引擎

### 16 个主题

```bash
# 浏览器内预览所有主题（并排对比 + 一键复制）
python3 toolkit/cli.py gallery

# 列出主题名称
python3 toolkit/cli.py themes
```

| 类别 | 主题 |
|------|------|
| 通用 | `professional-clean`、`minimal`、`newspaper` |
| 科技 | `tech-modern`、`bytedance`、`github` |
| 文艺 | `warm-editorial`、`sspai`、`ink`、`elegant-rose` |
| 商务 | `bold-navy`、`minimal-gold`、`bold-green` |
| 风格 | `bauhaus`、`focus-red`、`midnight` |

所有主题均支持微信暗黑模式。

### 微信兼容性自动修复

| 问题 | 自动修复 |
|------|---------|
| 外链被屏蔽 | 转为上标编号脚注 + 文末参考链接 |
| 中英混排无间距 | CJK-Latin 自动加空格 |
| 加粗标点渲染异常 | 标点移到 `</strong>` 外 |
| 原生列表不稳定 | `<ul>/<ol>` 转样式化 `<section>` |
| 暗黑模式颜色反转 | 注入 `data-darkmode-*` 属性 |
| `<style>` 被剥离 | 所有 CSS 内联注入 |

### 容器语法

````markdown
:::dialogue
你好，请问这个功能怎么用？
> 很简单，直接在 Markdown 里写就行。
:::

:::timeline
**2024 Q1** 立项启动
**2024 Q3** MVP 上线
:::

:::callout tip
提示框，支持 tip / warning / info / danger。
:::

:::quote
好的排版不是让读者注意到设计，而是让读者忘记设计。
:::
````

## 安装

**OpenCode**：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git ~/.opencode/skills/gzh-write
cd ~/.opencode/skills/gzh-write && pip install -r requirements.txt
```

**Claude Code**：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git ~/.claude/skills/gzh-write
cd ~/.claude/skills/gzh-write && pip install -r requirements.txt
```

**OpenClaw**（使用 `dist/openclaw/` 目录内容）：

```bash
git clone --depth 1 https://github.com/fonstone/gzh-write-skill.git /tmp/gzh
cp -r /tmp/gzh/dist/openclaw ~/.openclaw/skills/gzh-write
cd ~/.openclaw/skills/gzh-write && pip install -r requirements.txt
```

安装后 skill 会在每次运行时自动检查新版本。有更新时说"更新"即可升级。

### 配置（可选）

```bash
cp config.example.yaml config.yaml
```

填入微信公众号 `appid`/`secret`（推送需要）和图片 API key（生图需要）。不配也能用——自动降级为本地 HTML + 输出图片提示词。

### 为你的公众号定制风格

```bash
# 复制风格配置模板
cp style.example.yaml style.yaml
```

编辑 `style.yaml`，设置公众号名称、领域、写作人格、开头钩子、CTA 开关、排版主题等。首次运行时 GzhWrite 也会引导你完成设置。

## 快速开始

```
你：写一篇公众号文章
你：写一篇关于 AI Agent 的公众号文章
你：交互模式，写一篇关于效率工具的推文
你：帮我润色一下刚才那篇
你：学习我的修改                  → 飞轮学习
你：看看有什么主题                → 主题画廊
你：换成 sspai 主题               → 切换主题
你：看看文章数据怎么样            → 效果复盘
你：做一个小绿书                  → 图片帖（横滑轮播）
你：检查一下                      → 生成报告 + 质量自检
你：导入范文                      → 建立风格库
你：查看范文库                    → 查看已导入的范文
你：学习排版                      → 从公众号文章提取排版主题
```

## 目录结构

```
gzh-write-skill/
├── SKILL.md                    # 主管道（Step 1-8），OpenCode 原生格式
├── config.example.yaml         # API 配置模板
├── config.yaml                 # 当前配置（公众号API、图片生成、主题）
├── style.example.yaml          # 风格配置模板（含 opening_hook / cta_strict）
├── style.yaml                  # 当前风格（公众号名称、领域、人格、钩子、CTA、封面）
├── writing-config.example.yaml # 写作参数模板
├── VERSION                     # 版本号
├── requirements.txt            # Python 依赖
│
├── dist/openclaw/              # OpenClaw 兼容版（build_openclaw.py 构建）
│
├── scripts/                    # 数据采集 + 诊断 + 构建
│   ├── fetch_hotspots.py       # 多平台热点抓取（微博/头条/百度）
│   ├── seo_keywords.py         # SEO 关键词分析（百度 + 360）
│   ├── fetch_stats.py          # 微信文章数据回填
│   ├── build_playbook.py       # 从历史文章生成 Playbook
│   ├── learn_edits.py          # 学习人工修改（飞轮核心）
│   ├── humanness_score.py      # 文章质量打分（11 项检测）
│   ├── extract_exemplar.py    # 范文风格提取（SICO 式 few-shot 建库）
│   ├── learn_theme.py          # 从公众号文章 URL 提取排版主题
│   ├── fetch_article.py        # 从公众号 URL 提取正文为 Markdown
│   ├── diagnose.py             # 配置完备度检查
│   └── build_openclaw.py      # SKILL.md → OpenClaw 格式转换
│
├── toolkit/                    # Markdown → 微信工具链
│   ├── cli.py                  # CLI（preview / publish / gallery / themes / image-post）
│   ├── converter.py            # Markdown → 内联样式 HTML + 微信兼容修复
│   ├── theme.py                # YAML 主题引擎
│   ├── publisher.py            # 微信草稿箱 API + 小绿书图片帖
│   ├── wechat_api.py           # access-token / 图片上传
│   ├── image_gen.py            # AI 图片生成（9 provider，自动 fallback）
│   └── themes/                 # 16 排版主题（含暗黑模式，可从文章学习新增）
│
├── personas/                   # 6 套写作人格预设（含 opening_hook_options / view_switch / closing_components）
│   ├── ai-cultivator.yaml     # AI修炼者（技术深度拆解、类比驱动）
│   ├── midnight-friend.yaml   # 深夜好友（极度口语化、自我怀疑）
│   ├── warm-editor.yaml       # 温暖编辑（故事嵌套数据）
│   ├── industry-observer.yaml # 行业观察者（数据先行、稳中带刺）
│   ├── sharp-journalist.yaml  # 锐评记者（犀利简洁、强观点）
│   └── cold-analyst.yaml      # 冷静研究员（逻辑链条、风险意识）
│
├── references/                 # Agent 按需加载
│   ├── writing-guide.md        # 写作规范 + 开头钩子技法 + 视角切换 + AI 味戒律 + 信息密度节奏
│   ├── frameworks.md           # 通用五段式骨架 + 7 种写作框架
│   ├── content-enhance.md     # 4 增强策略 + 4 共性高分动作
│   ├── topic-selection.md      # 选题评估规则（引用三类钩子）
│   ├── seo-rules.md            # 微信 SEO 规则（三类标题钩子 + CTA 三要素）
│   ├── visual-prompts.md       # 视觉 AI 提示词规范
│   ├── wechat-constraints.md   # 微信平台限制 + 自动修复
│   ├── style-template.md       # 风格配置字段 + 16 主题列表
│   ├── exemplar-seeds.yaml     # 通用人类写作模式种子（无范文库时的 fallback）
│   ├── exemplars/              # 用户范文风格库（自动生成，不入 git）
│   ├── onboard.md              # 首次设置流程
│   ├── learn-edits.md          # 学习飞轮流程
│   └── effect-review.md        # 效果复盘流程
│
├── output/                     # 生成的文章
└── evals/                      # 评估用例
```

运行时自动生成（不入 git）：`style.yaml`、`history.yaml`、`playbook.md`、`writing-config.yaml`、`references/exemplars/*.md`

## 工作流程

```
Step 1  环境检查 + 加载风格（不存在则 Onboard）
  ↓
Step 2  热点抓取 → 历史去重 + SEO → 选题（含三类标题钩子标注）
  ↓
Step 3  框架选择（五段式骨架）→ 素材采集（webfetch 真实数据）→ 内容增强（4 策略 + 4 高分动作）
  ↓
Step 4  维度随机化 → 范文风格注入 → 写作（开头三法 + 视角切换 + 内容增强约束 + 真实素材锚定 + 编辑锚点 + AI 味戒律）→ 快速自检
  ↓
Step 5  SEO 优化（三类钩子 + CTA 三要素标注）→ 质量验证（含人话转译/横向对比/技术商业双视角/密度节奏）
  ↓
Step 6  视觉 AI（封面 + 内文配图，架构图/对比表/实测截图优先）
  ↓
Step 7  预检 + 排版 + 发布（16 主题 + 微信兼容修复）
  ↓
Step 8  写入历史 → 回复用户（含编辑建议 + 飞轮提示）
```

默认全自动。说"交互模式"可在选题/框架/配图处暂停确认。

## 多平台适配

源 SKILL.md 使用 OpenCode 原生格式（`todowrite` 任务追踪、`webfetch` 网页抓取、`{skill_dir}` 路径）。构建脚本自动转换为 OpenClaw 兼容格式：

```bash
# 构建 OpenClaw 兼容版本
python3 scripts/build_openclaw.py

# 输出到 dist/openclaw/，包含转换后的 SKILL.md 和所有资源文件
```

转换内容：`todowrite` → `TaskCreate`/`TaskUpdate`、`webfetch` → `web_search`、`{skill_dir}` → `{baseDir}`、移除 `allowed-tools`。

## Toolkit 独立使用

```bash
# Markdown → 微信 HTML
python3 toolkit/cli.py preview article.md --theme github

# 主题画廊
python3 toolkit/cli.py gallery

# 发布草稿箱
python3 toolkit/cli.py publish article.md --cover cover.png --title "标题"

# 小绿书/图片帖（横滑轮播，3:4 比例，最多 20 张）
python3 toolkit/cli.py image-post photo1.jpg photo2.jpg photo3.jpg -t "周末探店" -c "在望京发现的宝藏咖啡馆"

# 抓热点
python3 scripts/fetch_hotspots.py --limit 20

# SEO 分析
python3 scripts/seo_keywords.py --json "AI大模型" "科技股"

# 范文风格库
python3 scripts/extract_exemplar.py article.md              # 导入范文
python3 scripts/extract_exemplar.py *.md -s "你的公众号"     # 批量导入
python3 scripts/extract_exemplar.py --list                   # 查看范文库

# 文章质量检查
python3 scripts/humanness_score.py article.md --verbose

# 从公众号文章学习排版主题
python3 scripts/learn_theme.py https://mp.weixin.qq.com/s/xxxx --name my-style
```

## License

MIT