# Run: python3 fix_report_v2.py
# Patches the column width bug in report_v2.py
import os, re

path = os.path.expanduser("~/Desktop/cinerisk/report_v2.py")
with open(path) as f:
    code = f.read()

# Fix 1: KPI table — use fixed colWidths avoiding padding overflow
old = '    kt = Table(kpi_data, colWidths=[CW/4]*4)'
new = '    cw4 = (CW - 2) / 4\n    kt = Table(kpi_data, colWidths=[cw4]*4)'
code = code.replace(old, new)

# Fix 2: params table — tighter widths
old = '    pt=Table(params,colWidths=[36*mm,54*mm,36*mm,54*mm])'
new = '    pt=Table(params,colWidths=[34*mm,CW/2-34*mm,34*mm,CW/2-34*mm])'
code = code.replace(old, new)

# Fix 3: scenario table — recalculate to sum exactly to CW
old = '    sc=Table(srows,colWidths=[CW*.29,CW*.09,CW*.12,CW*.22,CW*.16,CW*.12])'
new = '''    _cw=CW
    sc=Table(srows,colWidths=[_cw*.28,_cw*.10,_cw*.12,_cw*.22,_cw*.16,_cw*.12])'''
code = code.replace(old, new)

# Fix 4: bar chart table
old = '    bt=Table(brows,colWidths=[54*mm,bw,CW-54*mm-bw])'
new = '    bt=Table(brows,colWidths=[50*mm,int(bw),CW-50*mm-int(bw)])'
code = code.replace(old, new)

with open(path, "w") as f:
    f.write(code)
print(f"Patched: {path}")
print("Now run:")
print('  python3 ~/Desktop/cinerisk/report_v2.py --genre action --hype high --strategy staggered --budget 180 --title "Nova Station" --client "Meridian Pictures"')
