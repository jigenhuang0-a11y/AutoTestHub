"""一键执行迁移 + 初始化 prompt"""
import subprocess, sys

commands = [
    ["python", "manage.py", "makemigrations", "agent_gateway", "--name", "add_prompt_config"],
    ["python", "manage.py", "migrate"],
    ["python", "manage.py", "seed_agent_prompts"],
]

for cmd in commands:
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.stderr:
        print("[STDERR]", r.stderr)
    if r.returncode != 0:
        print(f"!!! 命令失败，退出码: {r.returncode}")
        sys.exit(r.returncode)

print("\n✅ 全部完成！")
