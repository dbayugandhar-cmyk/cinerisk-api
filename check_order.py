"""
Run this anytime after editing detector_rtsp.py to verify function ordering.
Usage: python3 check_order.py
"""
import os, sys

path = os.path.expanduser('~/Desktop/cinerisk/theater/detector_rtsp.py')
content = open(path).read()
main_idx = content.find('\nif __name__')
after = content[main_idx:]

issues = []
for i, line in enumerate(after.split('\n')):
    if line.startswith('def ') or line.startswith('class ') or line.startswith('async def '):
        issues.append(f"Line {main_idx + i}: {line}")

if issues:
    print("ORDERING ISSUE — move these before if __name__:")
    for issue in issues:
        print(f"  {issue}")
    sys.exit(1)
else:
    print("OK — all functions correctly ordered")
