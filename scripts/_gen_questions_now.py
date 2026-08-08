"""快速生成80道预设测评题目"""
import os, sys, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_test_platform.settings'
django.setup()

from ai_evaluator.models import EvalTask, EvalQuestion
from accounts.models import User

# 获取管理员用户
admin = User.objects.filter(is_superuser=True).first() or User.objects.first()

CATEGORIES = [
    ("python", "Python编程", [
        "Python中GIL是什么？它对多线程程序有什么影响？",
        "解释Python的装饰器(Decorator)原理，并写一个带参数的装饰器示例。",
        "什么是Python的生成器(Generator)？它与列表推导式的区别？",
        "解释Python中的__new__和__init__的区别。",
        "如何实现一个线程安全的单例模式？给出两种方案。",
        "Python的async/await是如何工作的？与多线程有什么区别？",
        "解释元类(Metaclass)的概念及其应用场景。",
        "如何处理Python中的循环引用垃圾回收问题？",
    ]),
    ("database", "数据库", [
        "解释数据库事务的ACID特性，每个特性的含义是什么？",
        "什么是数据库索引？B+树索引的工作原理是什么？",
        "MySQL的InnoDB和MyISAM引擎有什么区别？各适合什么场景？",
        "解释数据库隔离级别，默认级别是什么？会产生哪些异常？",
        "什么是慢查询优化？你会从哪些方面排查？",
        "Redis和Memcached的区别？Redis有哪些数据类型？",
        "什么是数据库连接池？为什么需要它？",
        "解释CAP定理及其在分布式系统设计中的权衡。",
    ]),
    ("network", "计算机网络", [
        "TCP三次握手的过程是什么？为什么需要三次而不是两次？",
        "HTTP和HTTPS的区别？HTTPS的TLS握手过程是怎样的？",
        "什么是DNS解析？DNS查询的完整流程是怎样的？",
        "解释RESTful API的设计原则，什么是幂等性？",
        "WebSocket和HTTP长轮询的区别？各自适用场景？",
        "什么是CDN？它的原理和工作流程是怎样的？",
        "解释TCP的拥塞控制机制（慢启动、拥塞避免等）。",
        "什么是反向代理？Nginx作为反向代理的优势？",
    ]),
    ("security", "信息安全", [
        "SQL注入攻击的原理是什么？如何防范？",
        "XSS跨站脚本攻击有哪几种类型？如何防御？",
        "CSRF攻击的原理和防范措施？",
        "什么是JWT认证？它与Session认证的区别？",
        "解释OAuth 2.0的授权流程。",
        "如何安全地存储用户密码？bcrypt的工作原理？",
        "什么是中间人攻击(MITM)？如何通过证书固定防止？",
        "Docker容器的安全性考虑有哪些？",
    ]),
    ("devops", "DevOps/Docker", [
        "Docker镜像和容器的关系？Dockerfile常用指令有哪些？",
        "Docker Compose和Kubernetes的区别？各自适用场景？",
        "什么是CI/CD流水线？设计一个完整的部署流程。",
        "解释Git Flow工作流及各分支的作用。",
        "什么是蓝绿部署和金丝雀发布？各自的优缺点？",
        "如何监控生产环境的应用性能？常用的指标有哪些？",
        "解释微服务架构的优缺点，以及服务间通信方式。",
        "什么是基础设施即代码(IaC)？Terraform或Ansible的使用场景？",
    ]),
    ("git", "Git版本控制", [
        "Git中merge和rebase的区别？什么时候该用哪个？",
        "解释Git的工作区、暂存区和版本库的关系。",
        "什么是Git的cherry-pick？使用场景是什么？",
        "如何撤销一次已经push的commit？有哪些方法？",
        ".gitignore文件的编写规则？如何忽略已跟踪的文件？",
        "Git Hook有哪些？如何利用pre-commit做代码检查？",
        "什么是Git Submodule？什么时候会用到？",
        "解释Git bisect命令及其在bug定位中的作用。",
    ]),
    ("linux", "Linux运维", [
        "Linux文件权限(rwx)的数字表示方法？chmod和chown的区别？",
        "解释Linux进程状态(R/S/D/Z/T)的含义。僵尸进程怎么处理？",
        "什么是软链接和硬链接？它们的区别？",
        "top命令输出中各列的含义？如何找出CPU占用最高的进程？",
        "Shell脚本中$?、$$、$!、$#分别代表什么？",
        "grep/sed/awk三剑客的使用场景和基本用法？",
        "crontab定时任务的格式？如何调试定时任务？",
        "systemd和sysvinit的区别？如何管理systemd服务？",
    ]),
    ("frontend", "前端开发", [
        "Vue2和Vue3的核心区别？Composition API的优势？",
        "什么是虚拟DOM？Diff算法的基本原理？",
        "CSS的盒模型？标准盒模型和怪异盒模型的区别？",
        "什么是闭包(Closure)？它的实际应用场景和内存泄漏风险？",
        "Promise、async/await的错误处理最佳实践？",
        "前端性能优化的常见手段有哪些？",
        "Webpack打包优化策略？Tree Shaking和Code Splitting？",
        "SSR(服务器端渲染)和CSR的区别？Next.js/Nuxt.js的原理？",
    ]),
    ("algorithm", "数据结构与算法", [
        "时间复杂度和空间复杂度的分析方法？常见的复杂度等级？",
        "数组和链表的区别？什么场景选择哪个？",
        "哈希表的原理？解决冲突的方法有哪些？",
        "快速排序的时间复杂度？最坏情况如何优化？",
        "二叉树的前序/中序/后序遍历？递归和非递归实现？",
        "什么是动态规划？背包问题的基本思路？",
        "BFS和DFS的区别？分别在什么场景使用？",
        "红黑树和AVL树的比较？为什么HashMap用红黑树不用AVL？",
    ]),
    ("architecture", "系统设计", [
        "高并发系统的设计原则？如何应对流量洪峰？",
        "负载均衡的几种算法？LVS和Nginx的区别？",
        "分布式系统中如何保证数据一致性？CAP/BASE理论？",
        "消息队列(RabbitMQ/Kafka/RocketMQ)的选型和应用场景？",
        "缓存穿透/击穿/雪崩的原因及解决方案？",
        "如何设计一个短链接服务？考虑哪些因素？",
        "微服务架构中的服务发现和配置中心怎么做？",
        "数据库分库分表的策略？ShardingSphere的使用？",
    ]),
]

all_questions = []
for cat_id, cat_desc, presets in CATEGORIES:
    for q in presets:
        all_questions.append({
            "question": q,
            "expected_answer": "",
            "category": cat_id,
        })

task_name = f"综合技术能力测评 ({len(all_questions)}题)"
EvalTask.objects.filter(name=task_name).delete()

task = EvalTask.objects.create(
    name=task_name,
    description=f"覆盖{len(CATEGORIES)}个技术领域: Python/数据库/网络/安全/DevOps/Git/Linux/前端/算法/架构",
    target_type="custom_api",
    target_config={
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "headers": {"Authorization": "", "Content-Type": "application/json"},
        "body_template": {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "{question}"}],
            "temperature": 0.7,
            "max_tokens": 500,
        },
        "answer_path": "choices.0.message.content",
    },
    status="pending",
    total_questions=len(all_questions),
    created_by=admin,
)

qs = [EvalQuestion(
    task=task,
    index=i + 1,
    question=q["question"],
    expected_answer=q["expected_answer"],
    category=q["category"],
) for i, q in enumerate(all_questions)]
EvalQuestion.objects.bulk_create(qs)

print(f"[OK] Task created!")
print(f"  ID   = {task.id}")
print(f"  Name = {task.name}")
print(f"  Questions = {len(all_questions)}")
print(f"  Target = custom_api -> DeepSeek")
