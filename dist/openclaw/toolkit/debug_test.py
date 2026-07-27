from converter import WeChatConverter
import re

c = WeChatConverter(theme_name='github')
r = c.convert('# Test\n\n```python\ndef foo():\n    return 42\n```\n')

colors = re.findall(r'color:\s*([^;"<>]+)', r.html)
print('Colors found:', colors[:20])
print()
print('Has keyword span:', 'def' in r.html)
print('Has cf222e:', '#cf222e' in r.html)
print('Has 8250df (function):', '#8250df' in r.html)

idx = r.html.find('<pre')
if idx >= 0:
    end = r.html.find('</pre>', idx)
    print('\nCode block HTML:\n', r.html[idx:end+6][:500])
