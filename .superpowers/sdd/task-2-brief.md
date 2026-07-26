### Task 2: Update `SKILL.md` Step 2.1

**Files:**
- Modify: `SKILL.md` (lines 137-143)

- [ ] **Step 1: Replace Step 2.1 hot topic fetching**

Change the command and fallback in Step 2.1:

old:
```
**2.1 热点抓取**：

```bash
python3 {skill_dir}/scripts/fetch_hotspots.py --limit 30
```

**降级**：脚本报错 → 用 `webfetch` 访问热搜站点（微博热搜、今日头条、百度热搜）抓取热点
```

new:
```
**2.1 热点抓取**：

```bash
python3 {skill_dir}/scripts/fetch_aihot.py --limit 30 --mode {mode}
```

**降级**：脚本报错 → 用 `webfetch` 访问 aihot.virxact.com 页面抓取热点
```

- [ ] **Step 2: Verify the diff looks correct**

Run: `git diff`

Expected: Only the Step 2.1 block changed, no other content affected.
