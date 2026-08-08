"""后台运行 midscene 测试并记录输出"""
import os, sys, subprocess, shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
script_dir = Path(__file__).parent

result = subprocess.run(
    [sys.executable, '-u', str(script_dir / 'test_doubao_case.py')],
    capture_output=True,
    text=True,
    timeout=180,
    cwd=str(script_dir),
    env={**os.environ},
)

log_file = script_dir / 'doubao_output.txt'
with open(log_file, 'w', encoding='utf-8') as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== Exit: {result.returncode} ===\n")

# Print summary
lines = result.stdout.split('\n')
for i, line in enumerate(lines):
    if any(kw in line for kw in ['Status:', 'Error:', 'TEST COMPLETED', 'Exit code', 'Steps completed', 'Prompt:']):
        print(line)
    elif 'Step' in line and ('completed' in line or 'failed' in line):
        print(line)

print(f'\nFull log: {log_file}')
print(f'Exit: {result.returncode}')

if result.stdout:
    last_lines = result.stdout.split('\n')[-10:]
    print('\n--- Last 10 lines ---')
    for l in last_lines:
        print(l)
