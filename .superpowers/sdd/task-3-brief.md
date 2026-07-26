### Task 3: Update `references/topic-selection.md` scoring weights

**Files:**
- Modify: `references/topic-selection.md`

- [ ] **Step 1: Update scoring weights table**

Replace the 评估维度 section (around line 16-41).

old:
```
### 热度分（权重 30%）

看这个话题有多火：
- 热搜前 10 → 8-10 分
- 热搜 10-30 → 5-7 分
- 30 名之后 → 1-4 分
- 多个平台同时出现 → 加 2 分（封顶 10）

### 相关度分（权重 40%）

看这个话题跟客户定位有多契合：
- 直接命中 topics 列表 → 8-10 分
- 间接相关（比如客户做"AI"，热点是"芯片出口管制"）→ 5-7 分
- 勉强能扯上关系 → 3-4 分
- 完全无关 → 0 分
- **命中 blacklist 的词汇或话题 → 直接判 0，整个选题淘汰**

### 切入价值分（权重 30%）

看这个话题写出来能不能好看：
- 有明确的反直觉点或信息差 → 8-10 分
- 有争议、有正反两面可以讨论 → 6-7 分
- 纯资讯类、搬运即可 → 3-4 分
- 太复杂不适合 2000 字展开，或太浅没东西可写 → 1-2 分
```

new:
```
### 热度分（权重 20%）

看这个 AI 热点的时效性：
- 24 小时内 → 8-10 分
- 24-48 小时 → 5-7 分
- 48-72 小时 → 3-4 分
- 72 小时以上 → 1-2 分
- 无时间戳 → 5 分

### 相关度分（权重 40%）

看这个话题跟客户定位有多契合：
- 直接命中 topics 列表 → 8-10 分
- 间接相关（比如客户做"Agent"，热点是"Function Calling 更新"）→ 5-7 分
- 勉强能扯上关系 → 3-4 分
- 完全无关 → 0 分
- **命中 blacklist 的词汇或话题 → 直接判 0，整个选题淘汰**

### 切入价值分（权重 40%）

看这个话题写出来能不能好看：
- 有明确的反直觉点或信息差 → 8-10 分
- 有争议、有正反两面可以讨论 → 6-7 分
- 纯资讯类、搬运即可 → 3-4 分
- 太复杂不适合 2000 字展开，或太浅没东西可写 → 1-2 分

**category 加成**（基于 AI HOT 的分类）：
- `ai-models` / `ai-products`：若匹配 topics → 切入价值 +1
- `paper`：若 content_style 为干货 → 切入价值 +1
- `tip`：若 content_style 为情绪/观点 → 切入价值 +1
- 加成后封顶 10 分
```

Also update the `综合评分` formula:
old: `总分 = 热度 × 0.3 + 相关度 × 0.4 + 切入价值(含加成) × 0.3`
new: `总分 = 热度 × 0.2 + 相关度 × 0.4 + 切入价值(含加成) × 0.4`

- [ ] **Step 2: Verify**

Run: `git diff references/topic-selection.md`

Expected: scoring weights/descriptions changed, structure unchanged.
