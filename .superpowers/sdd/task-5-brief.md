### Task 5: Update theme CSS for code blocks

**Files:**
- Modify: `toolkit/themes/github.yaml`
- Modify: `toolkit/themes/tech-pro.yaml`

- [ ] **Step 1: Update github.yaml code block CSS**

In `base_css`, update `pre` and `pre code` styles:

Current:
```yaml
  pre {
    background: #f6f8fa;
    color: #1f2328;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 16px 0;
    line-height: 1.5;
    border: 1px solid #d1d9e0;
  }

  pre code {
    font-family: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 13.6px;
    background: none;
    color: #1f2328;
    padding: 0;
    border-radius: 0;
  }
```

Updated (add `font-size` to `pre` and adjust `pre code` font-family order):
```yaml
  pre {
    background: #f6f8fa;
    color: #1f2328;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 16px 0;
    line-height: 1.5;
    border: 1px solid #d1d9e0;
    font-size: 13.6px;
  }

  pre code {
    font-family: "SFMono-Regular", ui-monospace, Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 13.6px;
    background: none;
    color: inherit;
    padding: 0;
    border-radius: 0;
  }
```

- [ ] **Step 2: Update tech-pro.yaml code block border-radius**

In `base_css`, update `pre` border-radius from 4px to 6px:

old: `border-radius: 4px;`
new: `border-radius: 6px;`
