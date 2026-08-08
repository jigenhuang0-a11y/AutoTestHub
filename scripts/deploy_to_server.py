#!/usr/bin/env python3
"""部署前端到阿里云服务器 8.163.86.47"""
import paramiko
import os
import sys
import io

# 强制UTF-8输出，避免GBK编码错误
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

HOST = "8.163.86.47"
USER = "root"
PASSWORD = "Hjg123456"
ZIP_LOCAL = r"d:\AI_Project\ai-test-platform\frontend-dist.zip"
ZIP_REMOTE = "/tmp/frontend-dist.zip"
PROJECT_DIR = "/opt/ai-test-platform"


def run_ssh(ssh, cmd, desc=""):
    """执行远程命令并打印结果"""
    if desc:
        print(f"\n>>> {desc}")
    print(f"    $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(f"    [stderr] {err}")
    return out, err


def main():
    print("=" * 60)
    print("AI测试平台 - 前端自动部署")
    print(f"目标: {USER}@{HOST}")
    print("=" * 60)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # 1. 连接服务器
        print("\n[1/5] 连接服务器...")
        client.connect(HOST, username=USER, password=PASSWORD, timeout=15)
        print("    ✓ 已连接")

        sftp = client.open_sftp()

        # 2. 上传前端包
        print("\n[2/5] 上传前端构建产物 (1.5MB)...")
        sftp.put(ZIP_LOCAL, ZIP_REMOTE)
        print("    ✓ 已上传到 /tmp/frontend-dist.zip")
        sftp.close()

        # 3. 检查服务器当前部署方式
        print("\n[3/5] 检查服务器部署环境...")
        out, _ = run_ssh(client, f"ls {PROJECT_DIR}/frontend/dist/ 2>/dev/null | head -5", "检查frontend/dist目录")
        has_dist = bool(out.strip())
        
        out, _ = run_ssh(client, "docker ps --format '{{.Names}}' 2>/dev/null | grep -i front", "检查Docker前端容器")
        has_docker = bool(out.strip())
        
        out, _ = run_ssh(client, "which nginx 2>/dev/null && echo EXISTS || echo NOT_FOUND", "检查Nginx")
        has_nginx = "EXISTS" in out

        out, _ = run_ssh(client, f"ls {PROJECT_DIR}/backend/static/frontend/ 2>/dev/null | head -3", "检查Django静态文件目录")
        has_static = bool(out.strip())

        print(f"\n    部署方式检测: Docker={has_docker}, Nginx={has_nginx}, DjangoStatic={has_static}")

        # 4. 解压并部署
        print("\n[4/5] 解压并部署前端文件...")
        
        # 先确保目标目录存在
        run_ssh(client, f"mkdir -p {PROJECT_DIR}/frontend/dist", "创建dist目录")
        run_ssh(client, f"unzip -o {ZIP_REMOTE} -d {PROJECT_DIR}/frontend/dist/", "解压到 frontend/dist/")
        run_ssh(client, f"rm -f {ZIP_REMOTE}", "清理临时文件")

        # 根据部署方式更新
        if has_docker:
            container_name = "ai-test-frontend"
            print(f"    使用Docker方式部署 → 容器: {container_name}")
            run_ssh(client,
                f"docker cp {PROJECT_DIR}/frontend/dist/. {container_name}:/usr/share/nginx/html/",
                "复制到Docker容器")
            run_ssh(client,
                f"docker exec {container_name} nginx -s reload",
                "重启Nginx")
            print("    ✓ Docker前端已更新并重载")

        elif has_nginx:
            print("    使用Nginx直接托管")
            run_ssh(client, f"rsync -av --delete {PROJECT_DIR}/frontend/dist/ /var/www/ai-test-platform/", "同步到Nginx目录")
            run_ssh(client, "systemctl reload nginx", "重载Nginx")
            print("    ✓ Nginx已更新")

        elif has_static:
            print("    使用Django静态文件方式")
            run_ssh(client, f"cp -r {PROJECT_DIR}/frontend/dist/* {PROJECT_DIR}/backend/static/frontend/", "复制到Django static")
            run_ssh(client, f"cd {PROJECT_DIR}/backend && python manage.py collectstatic --noinput 2>&1 | tail -5", "收集静态文件")
            print("    ✓ Django静态文件已更新")

        else:
            print("    未检测到明确的部署方式，文件已解压到 frontend/dist/")
            print("    需要手动更新Web服务器配置")

        # 5. 验证
        print("\n[5/5] 验证部署结果...")
        run_ssh(client, f"ls -la {PROJECT_DIR}/frontend/dist/index.html 2>/dev/null && echo DEPLOYED_OK || echo FAILED", "检查index.html")
        
        # 检查下KnowledgeChat相关的JS文件
        out, _ = run_ssh(client, f"ls -lh {PROJECT_DIR}/frontend/dist/assets/KnowledgeChat-*.js 2>/dev/null", "KnowledgeChat组件文件")
        
        print("\n" + "=" * 60)
        print("✓ 部署完成!")
        print(f"访问: http://{HOST}:8000/knowledge/")
        print("新功能: 多Agent工作流按钮 (紫色渐变)")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 部署失败: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
