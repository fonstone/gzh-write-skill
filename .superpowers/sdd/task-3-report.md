# Task 3 Report: Update references/topic-selection.md scoring weights

**Status:** DONE

## Commits

- `904f4f3` — update topic-selection scoring weights for AI-specific data source

## Changes Applied

1. **Heat score** — weight 30%→20%, criteria changed from ranking-based (热搜前10/10-30/30+) to time-decay (24h/24-48h/48-72h/72h+)
2. **Relevance score** — weight stays 40%, example updated from "AI"/"芯片出口管制" to "Agent"/"Function Calling 更新"
3. **Insight score** — weight 30%→40%
4. **Category bonus** — new section added: `ai-models`/`ai-products`/`paper`/`tip` category bonuses
5. **Formula** — `总分 = 热度 × 0.2 + 相关度 × 0.4 + 切入价值(含加成) × 0.4`
6. **Tech mode table** — default weights synced (30%→20%, 30%→40%) for consistency

## Verification

- `git diff` confirms all intended changes; structure intact

## Concerns

None.
