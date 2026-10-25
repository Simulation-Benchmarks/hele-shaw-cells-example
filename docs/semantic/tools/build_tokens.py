"""Generate the atlas's CSS color and font tokens from the root DESIGN.md."""
import re
from pathlib import Path
root=Path(__file__).resolve().parents[3]
text=(root/'DESIGN.md').read_text()
colors=re.search(r'^colors:\n(.*?)^typography:',text,re.M|re.S)[1]
fonts=re.search(r'^typography:\n(.*?)^omitted:',text,re.M|re.S)[1]
lines=['/* Generated from DESIGN.md by tools/build_tokens.py. */',':root {']
for key,val in re.findall(r'^  ([\w-]+): "([^"]+)"',colors,re.M):lines.append(f'  --color-{key}: {val};')
for key,val in re.findall(r'^  ([\w-]+):\n    fontFamily: "([^"]+)"',fonts,re.M):lines.append(f'  --font-{key}: {val};')
lines.append('}')
(root/'docs/semantic/tokens.css').write_text('\n'.join(lines)+'\n')
