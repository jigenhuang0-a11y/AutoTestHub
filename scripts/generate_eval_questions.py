"""
批量生成测评题目并创建任务
用法: python scripts/generate_eval_questions.py [题目数量]
默认100道题，覆盖10个技术分类
"""

import sys
import os
import json
import requests
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from ai_evaluator.models import EvalTask, EvalQuestion


# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'

CATEGORIES = [
    ("python", "Python编程", [
        "Python GIL是什么？如何绕过GIL实现真正的并行计算？",
        "解释Python的装饰器原理，写一个带参数装饰器的示例",
        "Python中__new__和__init__的区别？什么场景用__new__？",
        "如何用asyncio实现并发HTTP请求？给出完整代码",
        "Python垃圾回收机制详解（引用计数+分代回收）",
        "描述符协议（descriptor）是什么？@property底层原理？",
        "metaclass元类的作用和使用场景举例",
        "contextlib.contextmanager与with语句的实现原理",
        "Python内存泄漏的常见原因及排查方法",
        "dataclass vs namedtuple vs NamedTuple的区别和选择",
    ]),
    ("database", "数据库", [
        "MySQL InnoDB引擎的MVCC实现原理是什么？",
        "什么是索引覆盖（Covering Index）？什么时候会触发？",
        "数据库事务的四大隔离级别分别解决什么问题？",
        "Redis持久化RDB和AOF各有什么优缺点？怎么选？",
        "MongoDB的分片（Sharding）策略有哪些？如何选择shard key？",
        "SQL慢查询优化的思路和常用方法（从explain开始）",
        "什么是数据库连接池？为什么需要它？HikariCP的优势？",
        "PostgreSQL的WAL（Write-Ahead Logging）机制详解",
        "数据库死锁的产生原因、检测方法和预防策略",
        "Redis集群模式Cluster vs 哨兵Sentinel对比",
    ]),
    ("network", "网络基础", [
        "TCP三次握手的过程是什么？为什么要三次而不是两次？",
        "HTTPS握手过程详细描述TLS1.3的优化点",
        "TCP拥塞控制算法（慢启动、拥塞避免、快速重传）详解",
        "DNS查询过程？什么是DNS缓存污染？如何防止？",
        "HTTP/2的多路复用是如何实现的？解决了HTTP/1.x的哪些问题？",
        "什么是CDN？CDN回源机制和缓存策略是怎样的？",
        "WebSocket和长轮询（Long Polling）的区别？适用场景？",
        "OSI七层模型每层的主要协议和功能",
        "负载均衡的几种算法（轮询、加权、一致性哈希等）",
        "QUIC协议相比TCP+TLS有什么优势？",
    ]),
    ("security", "网络安全", [
        "XSS攻击的类型和防御方法（存储型、反射型、DOM型）？",
        "CSRF攻击的原理和常见防护手段（Token、SameSite等）？",
        "SQL注入的原理？参数化查询为什么能防注入？",
        "什么是中间人攻击（MITM）？HTTPS如何防御MITM？",
        "OAuth2.0的四种授权流程分别适用于什么场景？",
        "JWT Token的结构和安全注意事项？",
        "DDoS攻击的常见类型（SYN Flood、HTTP Flood等）及防御？",
        "密码学中的对称加密和非对称加密的区别？RSA和AES的使用场景？",
        "什么是SSRF攻击？如何检测和防范服务端请求伪造？",
        "零信任架构（Zero Trust）的核心原则是什么？与传统边界安全有何不同？",
    ]),
    ("docker", "Docker容器", [
        "Docker镜像的分层存储原理？UnionFS的工作方式？",
        "Dockerfile的最佳实践（减少镜像层数、多阶段构建等）？",
        "Docker Compose和Docker Swarm vs Kubernetes的选择？",
        "容器逃逸的常见漏洞和防护措施？",
        "Docker网络的bridge/host/none/overlay模式的区别？",
        "docker exec和docker attach的区别？如何进入运行中容器调试？",
        "Docker的资源限制（CPU、Memory）是如何实现的？cgroup？",
        "私有镜像仓库Harbor的搭建和高可用方案？",
        "容器的健康检查（Healthcheck）配置和重启策略？",
        "Kubernetes中Pod、Deployment、Service的关系？",
    ]),
    ("git", "Git版本控制", [
        "Git rebase和merge的区别？什么时候该用rebase？",
        "Git reset --soft/mixed/hard三种模式有什么区别？",
        "Git cherry-pick的使用场景和注意事项？",
        "Git工作流比较：Git Flow vs GitHub Flow vs GitLab Flow？",
        ".gitignore的匹配规则？如何忽略已跟踪的文件？",
        "Git hook有哪些类型？pre-commit可以做什么自动化检查？",
        "Git stash的进阶用法？如何暂存部分文件？",
        "Git bisect如何用于快速定位引入bug的commit？",
        "Git submodule的管理方式和常见坑？",
        "Git LFS（Large File Storage）解决什么问题？如何配置？",
    ]),
    ("linux", "Linux运维", [
        "Linux进程状态有哪些？（R/S/D/Z/T/X等）僵尸进程如何处理？",
        "top命令各个指标的含义？load average怎么看？",
        "iptables防火墙规则的链和表结构？如何配置端口转发？",
        "systemd服务的单元文件结构？如何管理自定义服务？",
        "Linux文件权限rwx的数字表示？chmod/chown/sudo？特殊权限SUID/SGID/Sticky？",
        "Shell脚本中$? $$ $! $# $* $@等特殊变量的含义？",
        "awk和sed的常用操作？一行代码统计日志IP访问次数？",
        "/proc文件系统？如何通过/proc查看进程信息？",
        "crontab定时任务的格式？如何排查定时任务没执行的问题？",
        "SSH密钥认证配置？ssh-agent和ssh-add的作用？",
    ]),
    ("frontend", "前端开发", [
        "Vue3的Composition API相比Options API有什么优势？",
        "React Hooks中useEffect的依赖数组陷阱有哪些？",
        "虚拟DOM（Virtual DOM）的diff算法核心思想？key的作用？",
        "CSS Grid和Flexbox的区别？什么场景选哪个？",
        "浏览器的渲染流程（解析HTML→构建DOM→样式→布局→绘制→合成）？",
        "什么是事件冒泡和捕获？event.stopPropagation() vs stopImmediatePropagation()？",
        "Webpack打包优化手段（Tree Shaking、Code Splitting、懒加载等）？",
        "同源策略和跨域解决方案（CORS、JSONP、代理等）？",
        "前端性能优化指标（FCP、LCP、CLS、FID、TTI）？如何测量和优化？",
        "Service Worker离线缓存和Web Push Notification的实现？",
    ]),
    ("algorithm", "算法数据结构", [
        "时间复杂度O(1) O(log n) O(n) O(n log n) O(n^2)的典型场景举例？",
        "红黑树和B+树的区别？为什么MySQL用B+树做索引？",
        "HashMap的底层实现？Java8之后有什么改进？为什么线程不安全？",
        "快速排序的最坏情况？如何优化（三数取中、随机化）？",
        "动态规划的核心思想？背包问题的状态转移方程？",
        "布隆过滤器（Bloom Filter）的原理、误判率和使用场景？",
        "LRU缓存的实现方式（Hash Map + 双向链表）？",
        "图的最短路径算法：Dijkstra vs Bellman-Ford vs Floyd-Warshall？",
        "一致性哈希算法原理？在分布式系统中如何应用？",
        "跳表（Skip List）的查找复杂度和实现原理？",
    ]),
    ("architecture", "系统架构", [
        "微服务架构的利弊？服务拆分的粒度如何把握？",
        "CAP理论在分布式系统设计中如何权衡？BASE理论呢？",
        "消息队列（MQ）的作用？RabbitMQ/Kafka/RocketMQ的对比选型？",
        "API网关的功能有哪些？Kong/Nginx/Spring Cloud Gateway？",
        "服务发现和注册中心：Consul/Eureka/Nacos/Zookeeper对比？",
        "分布式事务的解决方案：2PC/TCC/Saga/本地消息表/Seata？",
        "高并发系统的设计原则？如何进行容量规划？",
        "缓存穿透、缓存击穿、缓存雪崩的原因和解决方案？",
        "读写分离和主从复制的架构设计？如何保证数据一致性？",
        "Serverless/FaaS架构的适用场景和限制？冷启动问题？",
    ]),
]


def generate_with_deepseek(category_name: str, category_desc: str,
                           count: int = 5) -> list[dict]:
    """调用DeepSeek生成指定分类的测评题目"""
    prompt = f"""你是一个专业的技术面试出题专家。请为「{category_desc}」领域生成 {count} 道高质量的测评题目。

要求：
1. 每道题包含 question（问题）和 expected_answer（标准答案要点）
2. 题目难度覆盖初级到高级
3. 答案要简洁但准确，包含关键得分点
4. 输出纯JSON数组格式，不要其他文字

输出格式：
[
  {{"question": "...", "expected_answer": "..."}},
  ...
]
"""

    resp = requests.post(
        DEEPSEEK_URL,
        headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 4000,
        },
        timeout=60,
    )

    if resp.status_code != 200:
        print(f"  ⚠ DeepSeek 调用失败: {resp.status_code} {resp.text[:200]}")
        return []

    content = resp.json()['choices'][0]['message']['content']
    # 解析JSON
    try:
        # 尝试提取JSON数组
        json_match = content.rfind('[')
        if json_match == -1:
            return []
        # 找到匹配的 ]
        bracket_count = 0
        end_pos = json_match
        for i in range(json_match, len(content)):
            if content[i] == '[':
                bracket_count += 1
            elif content[i] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i + 1
                    break
        items = json.loads(content[json_match:end_pos])
        return items
    except Exception as e:
        print(f"  ⚠ JSON解析失败: {e}")
        print(f"  原始内容: {content[:300]}")
        return []


def main():
    total_target = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    print(f"=" * 60)
    print(f"[START] 开始生成 {total_target} 道测评题目")
    print(f"=" * 60)

    all_questions = []
    per_category = max(total_target // len(CATEGORIES), 5)

    # 先用预设题目填充
    preset_used = set()
    for cat_id, cat_desc, presets in CATEGORIES:
        for q in presets:
            all_questions.append({
                'question': q,
                'expected_answer': '',  # 由LLM评分时不需要预设答案也可评
                'category': cat_id,
            })
            preset_used.add(cat_id)
            if len(all_questions) >= total_target * 0.6:  # 预设占60%
                break
        if len(all_questions) >= total_target * 0.6:
            break

    print(f"[OK] 已添加 {len(all_questions)} 道预设题目")

    # 不够的部分用 DeepSeek 动态生成
    remaining = total_target - len(all_questions)
    if remaining > 0:
        print(f"\n[DEEPSEEK] 正在调用 DeepSeek 补充生成 {remaining} 题...")

        gen_per_cat = max(remaining // len(CATEGORIES), 2)
        generated_total = 0

        for cat_id, cat_desc, _ in CATEGORIES:
            if generated_total >= remaining:
                break
            to_generate = min(gen_per_cat, remaining - generated_total)
            if to_generate <= 0:
                break

            print(f"\n  [{cat_desc}] 生成 {to_generate} 题...")
            items = generate_with_deepseek(cat_id, cat_desc, to_generate)
            for item in items:
                if isinstance(item, dict) and item.get('question'):
                    all_questions.append({
                        'question': item['question'],
                        'expected_answer': item.get('expected_answer', ''),
                        'category': cat_id,
                    })
                    generated_total += 1
                    if generated_total >= remaining:
                        break

        print(f"[OK] DeepSeek 生成了 {generated_total} 题补充")

    # 截断到目标数量
    all_questions = all_questions[:total_target]

    print(f"\n{'=' * 60}")
    print(f"[SUMMARY] 总计生成 {len(all_questions)} 道题目")
    print(f"{'=' * 60}")

    # 创建测评任务
    task_name = f"综合技术能力测评 ({len(all_questions)}题)"
    
    # 删除同名旧任务
    EvalTask.objects.filter(name=task_name).delete()

    task = EvalTask.objects.create(
        name=task_name,
        description=f"覆盖{len(CATEGORIES)}个技术领域的综合测评，含编程/数据库/网络/安全/DevOps/算法/架构等方向",
        target_type='custom_api',
        target_config={
            'api_url': 'https://api.deepseek.com/v1/chat/completions',
            'headers': {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json',
            },
            'body_template': {
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': '{question}'}],
                'temperature': 0.7,
                'max_tokens': 500,
            },
            'answer_path': 'choices.0.message.content',
        },
        status='pending',
        total_questions=len(all_questions),
    )

    # 批量创建题目
    question_objs = []
    for i, q in enumerate(all_questions):
        question_objs.append(EvalQuestion(
            task=task,
            index=i + 1,
            question=q['question'],
            expected_answer=q['expected_answer'],
            category=q['category'],
        ))
    EvalQuestion.objects.bulk_create(question_objs)

    print(f"")
    print(f"[OK] 测评任务已创建！")
    print(f"   任务名称: {task.name}")
    print(f"   任务ID:   {task.id}")
    print(f"   题目数量: {len(all_questions)}")
    print(f"   目标API:  DeepSeek (custom_api)")
    print(f"   分类分布:")

    from collections import Counter
    cat_counts = Counter(q['category'] for q in all_questions)
    for cat_id, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        cat_desc = next((d for c, d, _ in CATEGORIES if c == cat_id), cat_id)
        print(f"     - {cat_desc}: {count}题")

    print(f"")
    print(f"[TIP] 现在可以去前端刷新页面查看并执行此任务！")
    print(f"   API: POST /api/ai-evaluator/tasks/run_eval/ with body: {{\"task_id\": {task.id}}}")


if __name__ == '__main__':
    main()
