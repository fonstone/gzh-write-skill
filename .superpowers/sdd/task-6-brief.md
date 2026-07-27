### Task 6: Full integration test

- [ ] **Step 1: Run a full end-to-end test**

Run from the toolkit directory:

```bash
cd toolkit
python -c "
from converter import WeChatConverter

# Test with github theme
c1 = WeChatConverter(theme_name='github')
r1 = c1.convert('''# Test

## Code

```python
import os

class Foo:
    def bar(self, name: str) -> str:
        return f'hello {name}'

if __name__ == '__main__':
    print(Foo().bar('world'))
```

Inline: `os.path.join('a', 'b')`
''')
assert 'color: #cf222e' in r1.html, 'GitHub theme: no keyword coloring'
print('GitHub theme OK - keyword red found')

# Test with tech-pro theme
c2 = WeChatConverter(theme_name='tech-pro', tech_enhance=True)
r2 = c2.convert('''# Tech Test

```rust
fn main() {
    let x = 42;
    println!(\"{}\", x);
}
```
''')
assert 'pre' in r2.html, 'Tech-pro theme failed'
print('Tech-pro theme OK')

print('All integration tests passed')
"
```

Expected: Both themes render, keyword coloring visible in output.

- [ ] **Step 2: Test fetch_aihot.py runs**

```bash
python scripts/fetch_aihot.py --limit 3 --mode wechat
```

Expected: JSON output.
