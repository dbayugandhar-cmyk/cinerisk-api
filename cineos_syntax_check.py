import re, sys
c = open('cineos_internal.html').read()
lines = c.split('\n')
errors = []
for i, line in enumerate(lines, 1):
    if line.strip().startswith('<') or line.strip().startswith('//'):
        continue
    quotes = [j for j,ch in enumerate(line) if ch=="'" and (j==0 or line[j-1]!='\\')]
    if len(quotes)%2!=0 and len(line.strip())>10:
        errors.append(f'Odd quotes line {i}: {line[:80]}')
decls = re.findall(r'(?:let|const|var)\s+(\w+)\s*=', c)
from collections import Counter
skip = set(list('abcdefghijklmnopqrstuvwxyz')+['el','idx','res','map','qLow','vals','max','name','val','ri','flash','seen','b','r','n','q','c','d','t','s','p','f','k','v','w','m','x','j','o','h','g','u','i','e','color','sc','cc','by','bx','sev','cat','chain','attr','reach','phones','upis','ts','rs','steps','filtered','cnt','SC2','cls','icon','label','conf','text','html','score','node','edge','data','info'])
dupes = {k:v for k,v in Counter(decls).items() if v>1 and k not in skip}
for k,v in dupes.items():
    errors.append(f'Duplicate: {k} ({v}x)')
for fn in ['function doLogin','function loadAlerts','function switchTab','function invTab','function renderAilList','function runCR']:
    if fn not in c:
        errors.append(f'MISSING: {fn}')
if errors:
    print('ERRORS:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print(f'CLEAN — {len(lines)} lines')
    sys.exit(0)
