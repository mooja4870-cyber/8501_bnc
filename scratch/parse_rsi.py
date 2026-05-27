import subprocess

out = subprocess.check_output(['git', 'log', '-p', '--format=COMMIT|%cd|%s', '--date=iso', '--', 'core/config.py']).decode('utf-8', errors='ignore')

current_date = ''
current_msg = ''
changes = []

for line in out.split('\n'):
    if line.startswith('COMMIT|'):
        parts = line.split('|', 2)
        current_date = parts[1]
        current_msg = parts[2]
    elif 'RSI_OVERBOUGHT' in line or 'RSI_OVERSOLD' in line:
        if line.startswith('+') or line.startswith('-'):
            if not line.startswith('+++') and not line.startswith('---'):
                changes.append({'date': current_date, 'msg': current_msg, 'diff': line.strip()})

last_date = ''
for c in changes:
    if c['date'] >= '2026-05-26 23:45':
        if c['date'] != last_date:
            print(f"\n[{c['date']}] {c['msg']}")
            last_date = c['date']
        print(f"  {c['diff']}")
