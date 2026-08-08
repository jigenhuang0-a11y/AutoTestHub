# -*- coding: utf-8 -*-
"""
路特创新·AI算法测试工程师·500道深度递进式面试攻防题
每道题 L1→L2→L3→L4→L5 逐层深挖，不兜底，真刀真枪
直接输出 PDF
"""
import os, sys, re, textwrap, datetime

DATA = []
def S(title): DATA.append(("__SECTION__", title, ""))
def Q(q, a): DATA.append(("__QA__", q, a))

# ============================================================
# 第1章：AI测试平台项目深挖（Q1-Q80）—— 面试最核心战场
# ============================================================
S("第1章 AI测试平台项目深挖（Q1-Q80）——面试开场定生死")

S("1.1 平台架构全景（Q1-Q10）")

Q("Q1. 介绍一下你做的AI测试平台",
"""【L1·你的回答】
我做的是一个面向AI应用的自动化测试平台，核心三模块：
① Prompt评测——版本化管理(Git)，CI/CD自动化回归，变更后自动跑测试集对比指标
② RAG评测——集成RAGAS框架，评测Faithfulness/AnswerRelevancy/ContextPrecision/ContextRecall
③ Agent测试——模拟工具调用(正常/超时/异常/空结果)，验证Agent规划执行是否正确

技术栈：FastAPI + Celery(Redis Broker) + Vue3 + PostgreSQL + Milvus + Docker Compose
从0到1花了3个月：调研2周→MVP4周→迭代4周→推广2周

【L2追问】为什么选FastAPI不选Flask或Django？你没考虑到什么？
【L2·你的回答】
Flask是同步框架——AI API调用动辄几十秒，同步模式下1个请求占1个Worker，并发能力极差。虽然gevent能打补丁，但那是用户态协程(Greenlet切换)，遇到CPU密集操作(如大JSON解析)就阻塞整个进程——这叫"假异步"。

Django太重：ORM、模板引擎、中间件体系对纯API平台是冗余。Django的异步支持3.1才加，不如FastAPI原生。

FastAPI基于Starlette(ASGI)+Pydantic，原生async/await。asyncio基于OS事件循环(epoll/kqueue)，语言级await让渡控制权，比gevent的monkey patch可靠。加上自动Swagger文档+Pydantic类型校验，前后端联调效率高。

但我也知道局限：FastAPI社区比Flask小，某些第三方库(如Flask-Admin)没有等价物。如果要做复杂后台管理，可能需要额外引入方案。

【L3追问】你说gevent是"假异步"，那asyncio的await底层到底做了什么？事件循环是怎么调度协程的？
【L3·你的回答】
await触发时，CPython解释器做了几件事：
1. 当前协程(coroutine)被挂起，执行状态(栈帧/局部变量/IP指针)保存在协程对象中
2. 控制权交还给事件循环(Event Loop)
3. 事件循环调用epoll_wait()等待IO就绪事件
4. IO就绪后，事件循环从就绪队列取出协程，通过send()恢复执行

关键差异：gevent的Greenlet切换是用户态(setjmp/longjmp)，操作系统不知道你在切换。如果某个Greenlet里跑了CPU密集操作(如正则回溯)，它会一直占着CPU不放——操作系统认为这是一个线程在正常工作。

而asyncio的await是协作式的——只有显式await才会让出控制权。这也是asyncio的弱点：一个没有await的CPU密集函数会阻塞整个事件循环。解决方案是用run_in_executor()丢到线程池。

实际踩坑：我们曾在async路由里调了同步的requests.get()(而非aiohttp)，导致整个FastAPI服务卡死——因为requests.get()阻塞了事件循环，所有请求排队等这个函数返回。

【L4追问】那FastAPI的async路由和普通def路由在底层处理上有什么本质区别？什么场景该用哪个？
【L4·你的回答】
FastAPI内部用Starlette处理请求。区别在于线程池调度：

def路由(同步)：Starlette用run_in_threadpool()把函数丢到外部线程池(ThreadPoolExecutor)执行。默认线程池大小=40(可配置)。函数在线程里跑，不阻塞事件循环。适合：同步数据库查询(SQLAlchemy同步模式)、CPU密集计算。

async路由(异步)：直接在事件循环的协程里执行。适合：IO密集型操作(调用AI API/读写Redis/查询Milvus)。

误区：很多人以为async一定比def快。错。如果async路由里跑了同步代码(如没await的time.sleep(5))，它会阻塞整个事件循环5秒——比def路由更糟糕(def至少在线程池里不阻塞事件循环)。

我们的实践：AI API调用用async(aiohttp异步请求)，数据库操作用def(SQLAlchemy同步模式，走线程池)，评测任务触发后立即返回task_id(Celery异步处理)。

【L5追问】Starlette的run_in_threadpool底层用的什么线程池？和asyncio.to_thread()什么关系？线程池满了怎么办？
【L5·你的回答】
Starlette用concurrent.futures.ThreadPoolExecutor，通过anyio.to_thread.run_sync()调用。本质和asyncio.to_thread()一样——都是把函数提交给线程池。

线程池满的处理：
1. 默认ThreadPoolExecutor(max_workers=40)——第41个请求会排队等
2. 如果所有线程都在跑长时间同步操作(如大文件解析)，排队请求会超时
3. 解决方案：①增大max_workers(但线程切换开销也增大)；②改为async实现(用aiofiles替代同步IO)；③用Celery Worker做真正的异步处理

我们的方案：API路由只做参数校验+任务触发(返回task_id)，重活全丢Celery Worker。这样FastAPI的线程池永远不会成为瓶颈——因为API层不做重活。

这个设计理念叫"API层轻薄，Worker层厚重"——是异步架构的核心原则。""")

Q("Q2. 平台架构具体怎么分层的？每层之间怎么通信？",
"""【L1·你的回答】
四层架构：
① 接入层：Nginx(HTTPS终结/反向代理/静态资源)+前端Vue3 SPA
② API网关层：FastAPI BFF(认证JWT/参数校验/限流/路由编排)
③ 业务服务层：Prompt管理/评测执行/报告生成/Agent测试，模块化Python包
④ 基础设施层：PostgreSQL(业务数据)+Redis(缓存/Broker)+Milvus(向量)+Celery Worker(异步)+MinIO(文件)

层间通信：接入层→网关层(HTTP REST)，网关层→业务层(函数调用，通过Protocol/ABC接口抽象)，业务层→基础设施层(SDK/驱动)。上层不依赖下层具体实现。

【L2追问】这是微服务吗？每个服务独立部署？
【L2·你的回答】
严格说是"模块化单体"(Modular Monolith)，不是微服务。原因：
① 团队规模——我一人主导，微服务的分布式事务/服务发现/链路追踪运维复杂度ROI太低
② 业务耦合——Prompt评测和RAG评测共享数据集和评测结果表，拆分会增加跨服务调用延迟
③ 代码层面已做边界隔离——每个服务通过Protocol定义接口，内部实现独立。将来要拆，只需改DI配置+加RPC调用层

唯一"半独立"的是Celery Worker——独立进程，通过Redis Broker通信，已经是异步解耦。

【L3追问】你说的Protocol/ABC接口隔离具体怎么做的？和FastAPI的Depends依赖注入怎么配合？
【L3·你的回答】
示例代码结构：
```python
# core/interfaces.py
from abc import ABC, abstractmethod
class IEvaluationService(ABC):
    @abstractmethod
    async def run_evaluation(self, task_id: str) -> EvalResult: ...

# services/eval_service.py
class RAGASEvaluationService(IEvaluationService):
    async def run_evaluation(self, task_id):  # 真实实现

# api/deps.py
async def get_eval_service() -> IEvaluationService:
    return RAGASEvaluationService()  # DI容器配置

# api/eval_routes.py
@router.post("/eval")
async def create_eval(
    svc: IEvaluationService = Depends(get_eval_service)
):
    return await svc.run_evaluation(task_id)
```

关键点：FastAPI的Depends在请求级别解析依赖(每次请求都调用get_eval_service)，不是Spring那种进程级单例Bean管理。好处：单元测试时只需Mock get_eval_service返回Mock对象，不需要启动任何容器。

和Spring DI的本质区别：Spring DI是"容器管理Bean生命周期"（单例/原型/请求Scope，AOP代理），FastAPI Depends是"函数调用链"（无容器，无代理，更轻量）。

【L4追问】如果要换成微服务，你这个依赖注入方案怎么改造？服务间调用怎么处理？
【L4·你的回答】
改造路径：
1. Protocol接口保留不变——这是最关键的设计前瞻性
2. 实现类换成RPC客户端——如`RAGASEvaluationServiceClient`内部通过HTTP/gRPC调远程服务
3. DI层改配置——get_eval_service返回Client而非本地实现
4. 加服务发现——引入Consul/etcd，Client动态获取服务地址
5. 加容错——熔断器(pybreaker)、重试(tenacity)、超时控制

这就是"模块化单体"的价值：代码层面已经解耦，迁移成本低。如果一开始没做接口抽象，拆分时就需要大规模重构——那是噩梦。

【L5追问】gRPC和HTTP REST在微服务通信中各有什么优劣？你这个场景该用哪个？
【L5·你的回答】
gRPC优势：①Protobuf二进制序列化(比JSON小3-10倍，解析快5-10倍)；②HTTP/2多路复用(一个连接并发多个请求)；③强类型契约(.proto文件)；④原生支持流式(streaming)。劣势：①调试不便(二进制不可读)；②浏览器不能直接调(需grpc-web)；③学习成本。

REST优势：①可读可调试(curl/Postman直接测)；②浏览器原生支持；③生态工具多(API Gateway/文档/缓存)。劣势：①JSON序列化开销大；②弱类型(接口契约靠文档不靠代码)；③HTTP/1.1队头阻塞。

我们的场景选REST理由：①内部服务间调用的数据量不大(评测结果几十KB)；②调试便利性对早期项目很重要；③FastAPI原生REST支持好。如果将来有高吞吐场景(如实时推理结果流)，再考虑gRPC。选择原则：不是越先进越好，是越适合当前阶段越好。""")

Q("Q3. 项目从0到1怎么规划的？最大的决策失误是什么？",
"""【L1·你的回答】
4阶段3个月：
① 调研(2周)：对比LangSmith/LangFuse/RAGAS/DeepEval，输出选型报告
② MVP(4周)：Prompt评测模块先行，FastAPI+PostgreSQL基础架子，跑通后立刻内部试用
③ 迭代(4周)：加RAG评测、Grafana看板、Agent测试框架
④ 推广(2周)：文档+接入两个业务团队

最大失误：一开始选了Chroma做向量数据库，因为轻量上手快。数据量到几十万条后查询性能急剧下降——Chroma的HNSW索引是纯内存的，没有磁盘持久化优化。后来迁移到Milvus，写了数据迁移脚本(Chroma→JSON→Milvus)，花了一周。

教训：选型时要考虑"6个月后的数据规模"，而非"当前规模"。

【L2追问】Chroma和Milvus的具体性能差异在哪？迁移过程中遇到什么坑？
【L2·你的回答】
性能差异(我们实际测的数据)：
- 10万条向量：Chroma查询~10ms，Milvus~5ms，差异不大
- 50万条：Chroma~200ms(内存压力开始显现)，Milvus~8ms(IVF索引生效)
- 100万条：Chroma直接OOM或>2秒，Milvus~12ms
- Chroma在数据量>内存50%时性能断崖下降(Memory Swapping)

迁移坑：
① 向量精度——Chroma存的float32，Milvus也float32，但浮点序列化时精度微损，需验证(我们用余弦相似度差异<0.0001为阈值)
② Metadata映射——Chroma的metadata是dict，Milvus需建标量字段Schema，字段名不能有特殊字符(需清洗)
③ 批量写入——单条insert极慢，改用Milvus的bulk_insert(每批10000条)，速度从10条/s→10000条/s

【L3追问】Milvus的IVF_FLAT和HNSW索引内部数据结构分别是什么？各有什么trade-off？
【L3·你的回答】
IVF_FLAT(Inverted File with Flat compression)：
- 建索引：用K-Means聚类将向量空间分N个簇(N=nlist)，记录每个簇的中心点→倒排列表(簇ID→该簇所有向量)
- 查询：①算查询向量与所有簇中心的距离，选最近nprobe个簇；②在nprobe个簇内暴力搜索(Flat)
- Trade-off：nlist↑→建索引更快+内存更少，但精度↓(可能漏掉边界向量)；nprobe↑→精度↑但速度↓

HNSW(Hierarchical Navigable Small World)：
- 建图：多层跳表结构。上层节点稀疏(长距离连接)，下层密集(短距离连接)。节点随机分配层级(指数衰减概率：每层概率=1/M)
- 查询：从顶层入口点开始贪心搜索(每步选最近邻居)→逐层下降→底层精细搜索
- Trade-off：M↑(每节点连接数)→精度↑但内存↑；efConstruction↑→建图质量↑但建图时间↑

我们的选择：内存够用→HNSW(精度高+速度快)；向量量极大且内存紧张→IVF_FLAT(省内存，牺牲少量精度)。

【L4追问】HNSW图为什么能保证搜索精度？不会陷入局部最优吗？
【L4·你的回答】
HNSW不保证全局最优(精确最近邻)，它是近似算法。但精度高的原因：

① 多入口点——不是从单点开始，顶层有多个入口点(由插入顺序自然形成)，不同入口可能导向不同区域
② 启发式邻居选择——建图时不是只选最近M个，而是用启发式策略(如选"能覆盖不同方向"的邻居)，避免冗余连接
③ 贪心+回溯——搜索时维护一个候选集(大小=ef)，每步从候选集中选最近未访问节点继续搜索，自然有回溯能力

为什么不容易陷入局部最优？因为高维空间的"局部最优"概念本身就弱——高维向量空间中，贪心搜索已经很接近最优(这是高维空间的数学特性，叫"concentration of measure")。

但要承认：HNSW在某些极端分布(如簇间距极小)下确实可能漏掉真实最近邻。这是所有ANN(近似最近邻)算法的固有trade-off。

【L5追问】如果让你设计一个针对高维稀疏向量的索引，HNSW还适用吗？不适用的话怎么办？
【L5·你的回答】
HNSW对高维稀疏向量效果不好。原因：HNSW依赖距离比较(欧氏/余弦)，高维稀疏向量中距离度量失效(所有向量几乎等距——维数灾难)。且稀疏向量中大部分维度为零，图结构中大量冗余边。

替代方案：
① 倒排索引(Inverted Index)——传统搜索引擎用的。把向量看作"词袋"，每个非零维度对应一个倒排列表。查询时只扫描相关倒排列表。适合：TF-IDF/Bag-of-Words稀疏向量
② SPTAG/Bing搜索方案——微软的，结合树+图，对高维稀疏场景有优化
③ 混合检索——先用倒排索引粗筛候选，再用HNSW精排(前提：候选集已大幅缩小)

我们场景不涉及稀疏向量(embedding都是稠密的)，但架构上预留了混合检索能力——Milvus支持标量过滤+向量检索的混合查询。""")

Q("Q4. FastAPI项目结构怎么组织的？",
"""【L1·你的回答】
```
backend/
├── api/           # 路由层(薄)——按模块拆分(prompts/evaluations/reports/agents)
├── services/      # 业务逻辑层(厚)——prompt_service/eval_service/llm_client/ragas_service
├── models/        # 数据模型——db/(SQLAlchemy ORM) + schemas/(Pydantic DTO)
├── core/          # 核心配置——config/security/deps/middleware
├── tasks/         # Celery异步任务——eval_tasks/report_tasks
├── utils/         # 工具函数——logger/http_client/metrics
└── tests/         # 测试——按模块组织
```
原则：外层(api)薄——只做参数校验+依赖注入+返回响应；内层(services)厚——所有业务逻辑；数据模型严格分层(ORM不暴露给API，用DTO转换)。

【L2追问】llm_client怎么封装的？怎么支持多模型切换？
【L2·你的回答】
策略模式+工厂模式：

```python
# core/interfaces.py
class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, messages, **kwargs) -> LLMResponse: ...
    @abstractmethod
    async def chat_stream(self, messages, **kwargs) -> AsyncIterator[str]: ...

# services/llm_clients/
class OpenAIClient(BaseLLMClient): ...    # GPT-4/GPT-4o
class ClaudeClient(BaseLLMClient): ...    # Anthropic
class DeepSeekClient(BaseLLMClient): ...  # DeepSeek
class LocalVLLMClient(BaseLLMClient): ... # vLLM部署开源模型

# LLMResponse统一数据结构
@dataclass
class LLMResponse:
    content: str
    token_usage: dict  # {"prompt": 100, "completion": 50}
    finish_reason: str
    latency_ms: float
    model: str
```

工厂函数按配置选模型，加故障转移：主模型超时→自动切备用模型。配置驱动——改配置文件即可切换模型，不改代码。

【L3追问】你的故障转移(failover)机制具体怎么实现的？和熔断器怎么配合？
【L3·你的回答】
三层容错：

1. 重试层(Retry)：指数退避(1s→2s→4s→8s)，最多3次，只对可重试错误(超时/5xx/429限流)，不对4xx(参数错误)

2. 熔断层(Circuit Breaker)：三态模型
   - Closed(正常)：失败计数<阈值，请求正常通过
   - Open(熔断)：失败数达阈值→拒绝请求→直接抛异常(快速失败)
   - Half-Open(半开)：冷却期(30s)后→允许1个探测请求→成功则回到Closed，失败则继续Open
   
   用Redis做计数器(原子INCR+EXPIRE)，原因：Celery Worker多进程，内存计数器无法跨进程共享

3. 故障转移层(Failover)：主模型熔断→自动切备用模型。配置：
   ```yaml
   models:
     primary: {provider: openai, model: gpt-4o, timeout: 60s}
     fallback:
       - {provider: claude, model: claude-3.5-sonnet}
       - {provider: deepseek, model: deepseek-v3}
   ```

【L4追问】Redis做熔断计数器，Redis挂了怎么办？熔断器不就失效了？
【L4·你的回答】
好问题，这是生产环境的真实风险。我们的多层防护：

① 降级策略——Redis不可用时，熔断器降级为"进程内存计数器"。代价：多Worker间计数器不共享，熔断阈值变"每个Worker独立计数"。效果打折但不会完全失效
② 超时保护——连接Redis设置短超时(500ms)，超时就走降级，不影响正常请求
③ 监控告警——Redis连接失败率>1%→企业微信告警→人工介入

但这确实是当前方案的弱点。如果要彻底解决：
- 方案A：换RabbitMQ做Broker+RabbitMQ做熔断计数(一个基础设施搞定两个问题)
- 方案B：用Consul/etcd做分布式计数(强一致性但更重)
- 方案C：引入Sentinel这样的成熟熔断框架(功能全但引入Java依赖)

我们的选择：当前规模(日均几千次调用)下，Redis+降级够用。如果规模扩大，优先选方案A(RabbitMQ)，因为我们已经讨论过RabbitMQ作为Broker的需求。

【L5追问】Sentinel和Hystrix的熔断策略有什么本质区别？为什么Hystrix停更了？
【L5·你的回答】
Hystrix(Netflix)是熔断器模式的开创者，2018年进入维护模式(停更)。核心问题：
① 线程池隔离——每个依赖一个线程池，资源开销大(几百个依赖=几百个线程池)
② 架构僵化——难以扩展自定义熔断策略

Sentinel(阿里)的改进：
① 信号量隔离替代线程池隔离——更轻量，一个线程可管理多个依赖
② 滑动窗口统计——比Hystrix的桶(bucket)统计更精确(秒级精度 vs 10秒级)
③ 规则动态生效——配置变更实时推送，Hystrix需重启
④ 更丰富的流控规则——QPS/并发线程数/调用关系/热点参数

我们的熔断器参考了Sentinel的滑动窗口设计(Redis滑动窗口计数器)，但实现简单(未做慢调用比例熔断/未区分错误类型)。这符合"渐进式架构"原则——先用简单方案解决问题，复杂需求再引入成熟框架。""")

Q("Q5. 并发评测任务怎么处理？任务积压了怎么办？",
"""【L1·你的回答】
Celery异步任务架构：
FastAPI接收请求→生成task_id→提交任务到Redis Broker→立即返回task_id给前端
→多个Celery Worker并行消费任务→更新任务状态(PENDING→RUNNING→SUCCESS/FAILED)
→前端轮询GET /task/{task_id}/status获取进度

Worker配置：并发数=CPU核数×2(评测任务IO密集，大部分时间在等AI API返回)
任务路由(Task Routing)：快慢队列分离，快速任务(单个Prompt评测)和慢速任务(批量评测)不同队列，避免Head-of-Line阻塞

【L2追问】Redis做Broker，Redis挂了任务会不会丢？怎么保证可靠性？
【L2·你的回答】
多层防护：
① Redis AOF持久化——每条写操作记录到AOF文件，Redis重启后重放恢复数据。配置appendfsync=everysec(每秒刷盘，性能和安全平衡)
② 业务幂等——Worker执行任务前先查数据库，如果该task_id已经SUCCESS则跳过，防止重复执行
③ 超时重试——Celery配置soft_time_limit(任务执行超时上限)+定时任务扫描长时间RUNNING任务，重新入队
④ 任务结果存PostgreSQL——不依赖Redis存储结果

但承认局限性：Redis的AOF持久化是异步的，极端情况(断电)可能丢失最后1秒的数据。如果要求极高可靠性(任务零丢失)，应该换RabbitMQ(消息确认+持久化更成熟)。

【L3追问】RabbitMQ的ACK机制和Redis List做队列的本质区别是什么？消息可靠性模型？
【L3·你的回答】
本质区别在于消息语义：

Redis List(BRPOP)：消费者取出消息→消息立即从队列删除→消费者挂了→消息永久丢失。这是"At-Most-Once"语义(最多投递一次)。

RabbitMQ ACK：消费者取出消息→消息标记为unacked(未确认)→消费者处理完显式ACK→RabbitMQ才删除消息。消费者挂了→unacked消息自动重新入队(requeue)。这是"At-Least-Once"语义(至少投递一次)。

RabbitMQ额外保障：
① 消息持久化——消息写入磁盘(durable queue + persistent delivery mode)
② Publisher Confirm——生产者确认消息已被RabbitMQ接收(不是被消费)
③ 死信队列(DLX)——消息被拒绝/过期后进入死信队列，人工处理

Celery的补偿机制：应用层通过"数据库状态检查"做幂等，但这是应用层补偿，不是传输层保证。对于"任务零丢失"场景，Celery+RabbitMQ比Celery+Redis更可靠。

【L4追问】"At-Least-Once"意味着可能重复消费，你的业务幂等具体怎么实现的？分布式锁吗？
【L4·你的回答】
不是分布式锁，是数据库唯一约束+状态机：

```python
@celery_app.task(bind=True)
def run_evaluation(self, task_id: str):
    # 乐观锁方式——用数据库行级锁保证原子性
    with db_session() as session:
        task = session.query(EvalTask).filter(
            EvalTask.id == task_id
        ).with_for_update().first()  # SELECT ... FOR UPDATE
        
        if task.status in ('SUCCESS', 'FAILED'):
            return {"status": "already_done", "task_id": task_id}
        
        if task.status == 'RUNNING':
            # 检查是否是同一个Worker(防止僵死任务)
            if task.worker_id != self.request.hostname:
                return {"status": "locked_by_other_worker"}
        
        # 原子更新为RUNNING
        task.status = 'RUNNING'
        task.worker_id = self.request.hostname
        session.commit()
    
    # 执行实际评测...
    # 完成后更新为SUCCESS
```

关键设计：
① SELECT FOR UPDATE行级锁——保证同一task_id同时只有一个Worker能拿到
② worker_id检查——防止僵死任务(Worker挂了但状态还是RUNNING)被误判为重复
③ 状态机：PENDING→RUNNING→SUCCESS/FAILED，状态转换是单向的

比分布式锁好：不需要额外Redis依赖，利用PostgreSQL已有的事务机制。

【L5追问】SELECT FOR UPDATE在高并发下有什么问题？死锁风险怎么处理？
【L5·你的回答】
风险：
① 性能——FOR UPDATE锁住行直到事务结束，高并发下多个Worker排队等锁
② 死锁——如果事务内还更新其他表(如eval_results)，可能形成循环等待
③ 长事务——如果加锁后执行长操作(如调AI API)，锁持有时间过长

我们的防护：
① 锁粒度最小化——FOR UPDATE只锁task表一行，其他表操作用独立事务
② 锁定顺序一致——所有事务都先锁task再锁其他表(破坏循环等待条件)
③ 锁超时——PostgreSQL设置lock_timeout=5s，超时抛异常+重试
④ 不在持锁期间做IO——拿到锁→更新状态→立即提交→再执行AI调用(无锁状态)

实际上，Celery Worker数量不多(4-8个)，并发竞争不激烈，死锁几乎没出现过。但设计时考虑了最坏情况——这是后端工程师的肌肉记忆。""")

Q("Q6. 数据库怎么设计的？核心表结构和索引策略？",
"""【L1·你的回答】
四类核心表：
① Prompt管理：prompt_templates(id/name/version/content/status/created_at) + prompt_versions(版本历史，FK关联template)
② 评测任务：eval_tasks(task_id/type/status/total_cases/completed_cases/created_at) + eval_results(task_id/case_id/metrics(JSONB)/raw_response/latency_ms/model_used)
③ 测试用例：test_datasets(id/name/description) + test_cases(id/dataset_id/input/expected_output/tags(JSONB)/difficulty)
④ Agent测试：agent_tests + tool_simulations + agent_traces

索引策略：主键默认B-Tree，外键建索引，JSONB字段用GIN索引，时间范围查询用复合索引(status+created_at)

【L2追问】为什么用PostgreSQL而不是MySQL？你真正用到PG的哪些特性？
【L2·你的回答】
真正用到的PG特性：
① JSONB + GIN索引——eval_results的metrics存JSONB，可以查询"faithfulness<0.7的所有结果"，GIN索引让JSON内字段查询也能走索引。MySQL的JSON类型不能建真正的索引(虚拟列+普通索引是替代方案，不如GIN原生)
② CTE(WITH语句) + 窗口函数——30天趋势分析：WITH daily_stats AS (...) SELECT ... OVER(ORDER BY date)，比MySQL嵌套子查询清晰
③ pgvector扩展——后续考虑直接用PostgreSQL存embedding，不用单独部署Milvus(简化架构)
④ License——BSD协议，MySQL是Oracle GPL(合规风险)
⑤ 事务隔离级别——SERIALIZABLE做关键数据一致性保证

MySQL的优势是读性能(简单查询更快)，但我们的场景是分析型查询多(聚合/趋势/JSON查询)，PG更合适。

【L3追问】GIN索引的底层数据结构是什么？和B-Tree在JSON查询上的本质区别？
【L3·你的回答】
GIN(Generalized Inverted Index)——倒排索引：
- 结构：把复合数据(JSONB/数组/全文)分解成多个key→每个key指向包含它的行ID列表
- 对于JSONB：GIN索引提取JSON内所有key和value作为索引条目。查询`WHERE metrics @> '{"faithfulness": 0.85}'`时，GIN直接定位到包含"faithfulness"=0.85的行
- 和B-Tree区别：B-Tree索引整个字段值，对于JSONB只能建表达式索引`CREATE INDEX ON table ((metrics->>'faithfulness'))`——一个表达式一个索引，查询不同key需要不同索引。GIN一个索引覆盖所有key的查询

GIN的代价：①写入慢(每个key都要更新倒排列表)；②索引体积大(比B-Tree大3-5倍)；③VACUUM开销大

我们的场景：eval_results是"写一次读多次"，读远多于写，GIN的读优化是最佳选择。

【L4追问】PostgreSQL的GIN索引内部用的是什么数据结构？查询时怎么快速定位？
【L4·你的回答】
GIN内部结构：
① Entry Tree(B-Tree)——存所有索引key(如JSONB的每个键值对)，有序结构，O(log N)定位到key
② Posting Tree(B-Tree)或Posting List(数组)——每个key对应一组行ID(TID，元组ID)
   - 行数少→Posting List(压缩数组，顺序扫描)
   - 行数多→Posting Tree(B-Tree结构，二分查找)

查询流程：
1. 解析查询条件(如`@> '{"faithfulness": 0.85}'`)
2. 提取索引key："faithfulness"=0.85
3. 在Entry Tree中二分查找定位key
4. 获取对应的Posting Tree/List
5. 如果是多key查询(AND/OR)，对多个Posting List做交集/并集操作
6. 拿到TID列表→回表(Heap Fetch)取完整行

性能优化：GIN的fastupdate参数——写入先暂存到pending list(线性结构)，pending list满了再批量合并到Entry Tree。减少写入时B-Tree的随机IO。代价：查询时需同时扫描pending list(通常很小)。

【L5追问】PostgreSQL的MVCC机制对GIN索引有什么影响？VACUUM怎么处理GIN索引的死元组？
【L5·你的回答】
MVCC影响：PostgreSQL的更新=插入新版本+标记旧版本为死元组。GIN索引不直接存元组版本信息，存的是TID。当元组被标记为dead，GIN索引条目仍指向它。

查询时：GIN返回TID→回表检查可见性(通过xmin/xmax和事务快照判断)→不可见则跳过。这意味着：GIN索引可能返回"已死"的TID，需要回表过滤——这是额外开销。

VACUUM处理：
① 普通VACUUM：不清理GIN索引的死元组(因为GIN的Posting Tree清理需要全页扫描，开销大)
② VACUUM需要等pending list被合并后才清理
③ 真正清理靠gin_clean_pending_list()函数或autovacuum触发

长期不VACUUM的问题：GIN索引膨胀(死TID越来越多)→索引扫描返回大量无效TID→回表过滤开销增大→查询变慢

我们的运维：①开启autovacuum(默认开启)；②定期(每周)手动ANALYZE更新统计信息；③监控索引膨胀率(pg_stat_user_indexes.idx_scan vs idx_tup_fetch比例)""")

Q("Q7. 前端怎么做的？Vue3项目结构和状态管理",
"""【L1·你的回答】
Vue3 + Vite + Element Plus + Pinia + ECharts + Axios
项目结构：views/(页面) + components/(公共组件) + stores/(Pinia状态) + api/(接口封装) + router/(路由) + utils/(工具)

核心页面：Dashboard(ECharts趋势图+统计卡片) + Prompt管理(Monaco编辑器+版本对比) + 评测中心(创建任务+实时进度条) + 报告页(多维指标雷达图) + Agent测试(Trace树形展示)

Axios封装：请求拦截器(自动带Token)、响应拦截器(统一错误处理+401自动刷新Token)

【L2追问】为什么选Vue3不选React？真正的技术考量是什么？
【L2·你的回答】
真正的考量：
① 上手成本——考虑到可能有其他测试同事参与维护前端。Vue的SFC(Single File Component，template+script+style在一个文件)比React的JSX对非前端专业者更友好
② 响应式系统——Vue3的Proxy自动依赖追踪，数据展示密集场景(表格/表单/图表)下不需要手动优化。React需要useMemo/useCallback/memo来避免不必要渲染，心智负担更大
③ UI组件库——Element Plus对中后台场景(表格/表单/弹窗/菜单)支持最成熟。React的Ant Design也强，但Vue+Element Plus的组合在国内团队更普遍
④ 生态——Vite(尤雨溪做的构建工具)对Vue支持最好

不是React不好——React的Hooks/Fiber/Concurrent Mode非常先进。如果加入React团队，我能快速上手。选型是根据团队实际情况做决策。

【L3追问】React Fiber解决了什么问题？和Vue3的响应式更新机制的本质区别？
【L3·你的回答】
React Fiber解决的核心问题：可中断渲染。

React 15的Stack Reconciler是递归的——一旦开始diff，必须递归完整棵虚拟DOM树才能返回。长任务(大组件树)会长时间占主线程→用户交互卡顿→掉帧。

Fiber改造：
① 虚拟DOM树→Fiber链表(每个Fiber节点存return/child/sibling指针)
② Reconciler可中断——每处理一个Fiber节点检查是否有更高优先级任务(用户输入/动画)，有则暂停
③ Scheduler调度——时间切片(5ms)，到期让出主线程，下一帧继续
④ 双缓冲——Current树(当前显示)和WorkInProgress树(正在构建)，构建完成后一次性切换

Vue3的不同策略：
① 编译时优化——模板编译时标记动态节点(PatchFlag)，运行时只对比动态部分，静态节点直接跳过
② Proxy响应式——精确追踪哪个组件用了哪个数据，数据变化时只更新用到它的组件(靶向更新)
③ 没有Fiber——Vue3的更新是"知道哪些组件需要更新"，直接更新那些组件，不需要从根开始遍历

本质差异：React策略="全量计算但可中断"(不知道哪些变了，全算一遍但可以不阻塞)，Vue3策略="只算需要更新的"(知道哪些变了，精准打击)。这是两个不同的优化方向。

【L4追问】Vue3的Proxy响应式系统怎么追踪依赖的？和Vue2的Object.defineProperty有什么本质区别？
【L4·你的回答】
Vue2的Object.defineProperty：
- 遍历对象的每个属性，用getter/setter拦截
- getter里收集依赖(谁读了这个属性→记录到Dep)
- setter里触发更新(属性变化→通知Dep里的所有Watcher)
- 致命缺陷：①无法检测属性的添加/删除(新增属性无getter/setter)；②无法检测数组索引修改和length变化；③需要递归遍历所有属性(初始化慢)

Vue3的Proxy：
- 拦截整个对象(不是逐属性)，13种操作(包括set/get/deleteProperty/has/ownKeys等)
- get里用track()收集依赖(effect→Map<target, Map<key, Set<effect>>>)
- set里用trigger()触发更新(找到依赖此key的所有effect→执行)
- 优势：①天然支持属性添加/删除(deleteProperty被拦截)；②天然支持数组(index/length都被拦截)；③惰性响应(只对访问到的嵌套对象做reactive，不递归遍历)

依赖收集的数据结构：
WeakMap<Target, Map<Key, Set<ReactiveEffect>>>
- WeakMap：target→depsMap(目标对象→依赖映射)，WeakMap便于GC
- Map：key→effects(属性→副作用集合)
- Set：effects(去重的副作用集合)

这就是Vue3响应式系统的核心——三层嵌套的WeakMap/Map/Set结构。

【L5追问】Vue3的effect调度机制？computed和watch的底层实现区别？
【L5·你的回答】
effect是响应式系统的核心抽象——一个"副作用函数"及其依赖关系。

调度机制：
① 同步执行(effect默认)——依赖变化立即执行
② 异步批量(scheduler)——多个依赖同时变化，只执行一次effect(通过微任务队列Promise.then)
③ 组件渲染effect自带scheduler——多个响应式数据变化→组件只重新渲染一次(Vue3的nextTick基于微任务)

computed实现：
- 也是effect，但特殊处理：①lazy(创建时不立即执行)；②缓存(value+dirty标记，依赖不变返回缓存值)；③依赖收集(computed作为依赖被其他effect收集)
- 代码简化：new ReactiveEffect(getter, { scheduler: () => { dirty=true; trigger(computed) } })

watch实现：
- 创建effect包裹source(响应式数据或getter函数)
- scheduler里调用用户回调(newVal, oldVal)
- 特性：①支持深度监听(traverse递归收集依赖)；②支持immediate(立即执行)；③返回stop函数(清除effect)

本质区别：computed是"依赖变化→标记dirty→被访问时重新计算(懒)"，watch是"依赖变化→立即执行回调(急)"。

调度器的核心是用微任务队列(Microtask)合并更新——这和Vue2的nextTick一样，但Vue3的实现更干净(没有watcher队列的复杂排序)。""")

Q("Q8. 认证和权限怎么做的？JWT的无状态性带来了什么问题？",
"""【L1·你的回答】
JWT方案：登录→后端验证用户名密码→签发JWT(含user_id/role/exp)→前端存localStorage→每次请求Header带Authorization: Bearer <token>→后端验证签名+过期时间

RBAC三种角色：Admin(管理用户+全数据访问)、Editor(创建编辑+发起评测)、Viewer(只看报告)

FastAPI Depends做权限校验：`def require_role(role): return Depends(lambda current_user=Depends(get_current_user): check_role(current_user, role))`

【L2追问】JWT过期了怎么刷新？无感刷新怎么做？
【L2·你的回答】
双Token机制：
- Access Token：短期(30分钟)，存localStorage，每次请求携带
- Refresh Token：长期(7天)，存localStorage(或httpOnly cookie更安全)，存在数据库

无感刷新流程：
① Axios响应拦截器捕获401错误
② 检查是否是Access Token过期(而非无权限)
③ 用Refresh Token调POST /auth/refresh
④ 后端验证Refresh Token(查数据库+验签名)
⑤ 返回新Access Token+新Refresh Token(Rotation)
⑥ 拦截器更新localStorage中的Token
⑦ 用新Access Token重试原请求
⑧ 用户完全无感知

Refresh Token Rotation：每次刷新都换新Refresh Token，旧Token失效。好处：如果Refresh Token被盗，正常用户下次刷新时旧Token失效→盗用者持有的旧Token也失效→安全窗口从7天缩短到30分钟。

【L3追问】JWT的吊销问题——用户改密码后，已签发的JWT怎么让它失效？
【L3·你的回答】
这是JWT无状态性最大的痛点——Token一旦签发，在过期前一直有效，服务端无法主动吊销。

解决方案(按复杂度递增)：

① 缩短有效期——Access Token有效期5-10分钟，即使不吊销，风险窗口也只有10分钟。代价：刷新频率高

② Redis黑名单——改密码/登出时，把Token的jti(JWT ID)存入Redis黑名单(过期时间=Token剩余有效期)。每次请求验证Token时先查黑名单。代价：每个API请求多一次Redis查询(但可缓存)

③ 版本号方案——用户表加token_version字段。JWT payload包含token_version。改密码→DB中token_version+1→旧JWT的version不匹配→拒绝。代价：每次请求需查DB(用户表)，但用户数据通常已缓存

④ Refresh Token短周期——Refresh Token有效期30分钟而非7天。Access Token过期→用Refresh Token刷新→如果Refresh Token也被吊销(数据库中标记)→刷新失败→用户重新登录

我们的方案：方案①+②组合。Access Token 30分钟+Redis黑名单(改密码时加入)。因为：用户量不大(内部平台)，Redis查询不是瓶颈。且改密码是低频操作。

【L4追问】如果Redis黑名单丢了(Redis挂了/重启了)，黑名单不就失效了？这有安全风险吧？
【L4·你的回答】
确实有风险，我们的多层缓解：
① Redis持久化——RDB+AOF双保险，重启后恢复黑名单数据
② 黑名单写优先——改密码操作：先写Redis黑名单(同步，等待ACK)→再更新DB密码。如果Redis挂了→改密码操作直接失败→提示用户稍后重试
③ 降级到DB——Redis不可用时，查询黑名单降级为查DB(token_blacklist表)。慢但不会漏
④ Access Token短周期——最坏情况(Redis和DB都挂了)，30分钟后旧Token自动过期

安全是一个概率游戏，不是0和1。我们的目标是"把风险窗口缩到可接受范围"，不是"绝对安全"。30分钟窗口+Redis持久化+降级策略，在内部平台场景下风险可控。

如果要金融级别的安全：用有状态的Session替代无状态的JWT。每次请求查Session Store(Redis/DB)，可随时吊销。代价：失去了JWT的分布式无状态优势。

【L5追问】OAuth2.0的授权码模式(Authorization Code)和JWT是什么关系？你的平台如果用OAuth2.0会怎么设计？
【L5·你的回答】
关系：OAuth2.0是授权框架(定义角色/流程/Token类型)，JWT是Token格式(数据结构)。OAuth2.0的Access Token可以用JWT格式(自包含，无状态)，也可以用Opaque Token(随机字符串，需查授权服务器)。

OAuth2.0授权码流程(最安全的模式)：
① 用户点击"企业微信登录"→重定向到企业微信授权页
② 用户授权→企业微信回调我们的redirect_uri+授权码(code)
③ 后端用code+client_secret换Access Token(服务端间通信，code不暴露给前端)
④ 后端拿到Access Token→调企业微信API获取用户信息→匹配内部用户→签发我们自己的JWT

为什么授权码模式最安全：
- code只使用一次+短期有效(几分钟)
- code通过后端信道交换(不经过浏览器)，且需要client_secret(前端拿不到)
- 隐式模式(Implicit)已废弃——Token直接返回到浏览器(URL fragment)，安全风险大

我们的平台改造方案：
① 接入企业微信/飞书OAuth2.0(路特创新可能用企业微信)
② 首次登录自动创建用户(映射企业微信UserID→平台账号)
③ 保留现有的JWT方案(内部Token)，OAuth2.0只用于身份认证
④ 支持多IdP(Identity Provider)——企业微信/飞书/GitHub，策略模式切换

核心原则：OAuth2.0管"你是谁"(Authentication)，我们自己管"你能做什么"(Authorization/RBAC)。""")

Q("Q9. Docker Compose部署架构？适合生产环境吗？",
"""【L1·你的回答】
docker-compose.yml定义所有服务：
- nginx：前端静态资源+反向代理
- backend：FastAPI应用
- celery_worker：Celery Worker(可scale)
- celery_beat：定时任务调度
- postgres：PostgreSQL 15
- redis：Redis 7
- milvus：Milvus standalone

服务间通过Docker网络通信(服务名=hostname)，环境变量.env区分环境，数据卷挂载做持久化。

【L2追问】Docker Compose适合生产吗？服务挂了怎么恢复？
【L2·你的回答】
单机小规模可用，但需额外配置：
① restart: unless-stopped——Docker守护进程重启后自动启动容器
② healthcheck——每个服务定义健康检查(backend: curl /health, postgres: pg_isready, redis: redis-cli ping)
③ depends_on + condition: service_healthy——确保启动顺序(PostgreSQL就绪后再启Backend)
④ 日志轮转——配置max-size/max-file防止日志撑爆磁盘
⑤ 资源限制——mem_limit/cpus防止单个容器吃光资源

局限：
- 不能跨机(单机部署)
- 无服务发现(靠静态hostname)
- 无负载均衡(单实例)
- 滚动更新需手动操作(docker compose up -d会短暂中断)

当前阶段(内部平台，几十个用户)够用。将来需多机部署时迁移K8s。

【L3追问】如果迁移K8s，需要做哪些改造？应用代码要改吗？
【L3·你的回答】
应用代码不需要改(这是关键！)，只改部署配置：

① 配置管理：.env→ConfigMap(非敏感)+Secret(敏感，如数据库密码/API Key)
② 服务发现：Docker hostname→K8s Service DNS(<service>.<namespace>.svc.cluster.local)
③ 持久化存储：Docker volume→PVC(PersistentVolumeClaim)
④ 健康检查：Docker healthcheck→livenessProbe(存活探针)+readinessProbe(就绪探针)
⑤ 水平扩展：Celery Worker Deployment→HPA(HorizontalPodAutoscaler)按队列长度伸缩
⑥ 入口流量：Nginx→K8s Ingress Controller(Nginx Ingress/Traefik)
⑦ 监控：Prometheus Operator + Grafana + Loki(日志)
⑧ 定时任务：Celery Beat→K8s CronJob(或保留Celery Beat Deployment单副本)

K8s Manifest示例：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: worker
        image: registry.example.com/celery-worker:latest
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secret
```

原则：12-Factor App，配置与代码分离。我们的应用已经是这样设计的(环境变量读取配置)，迁移K8s只是换配置来源。

【L4追问】K8s的Service和Docker Compose的hostname在DNS解析上有什么本质区别？Service Mesh(Istio)解决了什么问题？
【L4·你的回答】
Docker Compose DNS：基于Docker内置DNS服务器(127.0.0.11)。容器名=hostname，解析为容器IP。问题：①容器重启IP变化→DNS缓存(TTL)导致短暂不可达；②无负载均衡(一个hostname→一个IP)；③无健康检查联动(挂了也解析)

K8s Service DNS：CoreDNS监听API Server→Service和Pod变化实时更新。Service的Cluster IP是虚拟IP(由kube-proxy通过iptables/IPVS实现负载均衡)。特点：①VIP稳定(Service不重启IP不变)；②自动负载均衡到健康Pod(配合readinessProbe)；③支持会话亲和性(sessionAffinity)

Service Mesh(Istio/Linkerd)解决的问题：
① 细粒度流量控制——金丝雀发布(10%流量到新版本)、A/B测试、熔断/超时/重试(在Sidecar层，不需应用代码改)
② 可观测性——自动注入分布式追踪(Jaeger/Zipkin)+指标(Prometheus)+访问日志
③ 安全——mTLS(服务间通信自动加密)+RBAC(哪些服务可以调哪些)
④ 多集群通信——跨K8s集群的服务发现和路由

代价：复杂度大增(每个Pod注入Sidecar容器)，性能损耗(每个请求多两跳网络)，运维成本高。我们的规模不需要Service Mesh，简单Ingress+CoreDNS就够了。这是"够用就好"原则。

【L5追问】K8s的Pod网络模型和Docker的网络模型有什么本质区别？CNI插件(Calico/Flannel)做了什么？
【L5·你的回答】
Docker网络模型：默认bridge模式——每个容器一个虚拟网卡(veth pair)，通过docker0网桥通信，NAT出宿主机。跨主机需overlay网络(Swarm的VXLAN)。

K8s Pod网络模型(CNI规范)：
① 每个Pod有独立IP(不是每个容器，同Pod内容器共享网络命名空间+共享IP)
② Pod间直接通信(不需要NAT，所有Pod在一个扁平网络空间)
③ Node上的Pod可以和Node上所有Pod通信

CNI插件负责实现这个模型：

Flannel(简单)：
- 每个Node分配子网(Node1: 10.244.1.0/24, Node2: 10.244.2.0/24)
- 跨Node通信：VXLAN封装(原始包→UDP包→物理网络→解封装)或host-gw(直接路由，要求二层互通)
- 优点：简单，缺点：无网络策略(NetworkPolicy)

Calico(高性能)：
- 不用overlay(默认)——用BGP协议在各Node间交换路由信息，纯三层路由(Pod IP直接在物理网络路由)
- NetworkPolicy支持——基于iptables实现Pod级别防火墙规则
- 优点：性能好(无封装开销)，功能全；缺点：需要网络设备支持BGP(或IPIP隧道)

性能差异：Calico(无封装) ≈ 原生网络性能；Flannel VXLAN ≈ 原生90-95%(封装开销)；Flannel host-gw ≈ Calico(但限制更多)。

我们的选择：如果是云上K8s(如腾讯云TKE)，用云厂商的CNI(如VPC-CNI，Pod直接用VPC IP，性能最优)。这是"云原生"的实践。""")

Q("Q10. 日志和可观测性怎么做的？排查问题最常用的日志技巧？",
"""【L1·你的回答】
三层可观测：
① 日志——结构化JSON日志(Python logging)，包含request_id/user_id/module/timestamp/level/message。输出stdout，Docker/Daemon收集
② 指标——Prometheus+Grafana。基础设施指标(Node Exporter: CPU/内存/磁盘)，应用指标(prometheus_fastapi_instrumentator: QPS/延迟/错误率)，业务指标(评测任务完成数/成功率，推Pushgateway)
③ 链路追踪——在LLM调用/检索/Tool执行关键节点插hook，记录输入输出+耗时+token消耗。用contextvars传递trace_id(异步安全)

【L2追问】为什么用Pushgateway推送Celery指标？Prometheus的拉模式不是更好吗？
【L2·你的回答】
Prometheus设计是拉模式(Pull)——定时从Target抓取/metrics端点。但Celery Worker是短生命周期进程(任务完成就空闲，没有HTTP端口暴露/metrics)，Prometheus来不及拉取。

Pushgateway作为中间缓冲：Worker完成任务→把指标推送到Pushgateway→Prometheus从Pushgateway拉取。

踩过的坑：
① 指标残留——Worker异常退出时，Pushgateway里该Worker的指标永远存在(不会自动过期)→Grafana图表显示错误数据。解决：任务结束时推送"0值"覆盖旧指标，或Pushgateway设置指标过期时间
② 单点故障——Pushgateway挂了，所有Worker指标丢失。当前单机部署风险可控
③ 指标名冲突——多个Worker同时推送同名指标→后推送的覆盖前一个。解决：标签区分(instance=worker_hostname)

生产级替代：Grafana Agent(支持Push模式，更可靠)或VictoriaMetrics(兼容Prometheus但支持Push)

【L3追问】你说的contextvars传递trace_id，和OpenTelemetry的Context Propagation什么关系？如果跨服务了怎么办？
【L3·你的回答】
contextvars是Python 3.7+引入的标准库，提供协程安全的上下文变量(类似ThreadLocal但适配asyncio)。原理：
- 每个协程有独立的Context(类似os.environ的key-value存储)
- await创建子协程→自动复制父协程的Context(copy-on-write)
- 设置trace_id = ContextVar('trace_id')，在中间件设置值，所有下游代码通过trace_id.get()获取

OpenTelemetry的Context Propagation：
- 跨进程传播(HTTP Header: traceparent: 00-trace_id-span_id-01)
- 服务A调用服务B→trace_id放在HTTP Header传递→服务B提取trace_id→保持全链路追踪

我们的当前实现是"单进程版"的链路追踪(只在本服务内传递trace_id)。如果要跨服务：
① 引入OpenTelemetry SDK——自动在HTTP Client请求时注入traceparent Header
② 引入Jaeger/Zipkin——收集各服务的Span数据，拼成完整Trace
③ 不改业务代码——OpenTelemetry的自动检测(auto-instrumentation)可自动为FastAPI/Redis/HTTP Client生成Span

但当前单服务架构不需要，设计预留了扩展点(contextvars方案和OpenTelemetry兼容——contextvars存的trace_id可以和OpenTelemetry的SpanContext打通)。

【L4追问】排查"评测任务跑了30分钟没结果"这种问题，你怎么定位？看什么日志？
【L4·你的回答】
标准排查链路：

① 查任务状态——`SELECT * FROM eval_tasks WHERE task_id='xxx'`→确认状态(是否卡在RUNNING)
② 查Celery日志——`docker logs celery_worker | grep "task_id=xxx"`→看Worker是否接收到任务/执行到哪一步
③ 查AI API调用日志——看LLM调用的请求和响应时间，判断是否AI API超时/无响应
④ 查Redis——`redis-cli LLEN celery`→看任务队列是否积压(说明Worker处理不过来)
⑤ 查系统资源——`docker stats`→CPU/内存是否打满(可能OOM导致Worker僵死)

日志设计的核心：每条日志必须包含request_id/task_id(可grep串联)。结构化的JSON日志可以用jq过滤：`docker logs backend | jq 'select(.task_id=="xxx")'`

【L5追问】如果Worker僵死了(进程在但不处理任务)，怎么自动发现并恢复？
【L5·你的回答】
多层监控和自动恢复：

① Celery自带——worker_lost_wait超时(Worker心跳丢失超过阈值→Broker认为Worker死亡→任务重新分配)
② 任务超时——soft_time_limit(抛出SoftTimeLimitExceeded，任务可捕获做清理)+time_limit(硬杀进程)
③ 内存泄漏防护——worker_max_memory_per_child(处理N个任务后重启Worker进程，释放泄漏内存)
④ 外部监控——Celery Beat定时任务检查：
   - 超过N分钟状态仍为RUNNING的任务→可能是僵死Worker→强制重新入队
   - 队列积压超过阈值→企业微信告警→手动扩容Worker
⑤ 进程监控——Supervisor/systemd管理Worker进程，挂了自动重启

关键：设置合理的超时和告警阈值。评测任务正常耗时5-20分钟(取决于评测量)，超时设30分钟。监控"RUNNING超过30分钟"的任务比例，超过5%告警。

经验之谈：Celery Worker的"假死"问题(进程在但事件循环阻塞)是最难排查的——日志不输出，心跳正常但任务不处理。原因通常是：①同步阻塞调用(如没用异步的HTTP Client)；②死锁(数据库连接池耗尽)。排查用`py-spy dump -p <pid>`看Python线程堆栈，定位阻塞点。""")

print(f"[OK] 第1章 1.1节完成 (Q1-Q10)")

# ============ 1.2 技术选型与架构决策（Q11-Q25）============
S("1.2 技术选型与架构决策（Q11-Q25）")

Q("Q11. 你做过哪些关键的技术选型？选型方法论是什么？",
"""【L1·你的回答】
关键选型：后端框架FastAPI(vs Flask/Django)、AI编排LangChain(vs LlamaIndex/原生SDK)、评测框架RAGAS(vs DeepEval)、向量数据库Milvus(vs Chroma/Pinecone/Qdrant)、消息队列Redis(vs RabbitMQ)、部署Docker Compose(vs K8s)、前端Vue3(vs React)。

选型方法论：五维评估——①功能匹配度(核心需求能否满足)；②学习成本(团队能否hold住)；③生态成熟度(社区/文档/案例)；④性能与扩展性(6个月内的预期规模)；⑤成本(开源/付费/运维人力)。权重根据项目阶段动态调整——早期更看重开发效率，成熟期更看重稳定性。

【L2追问】有没有选错的案例？后来怎么纠正的？
【L2·你的回答】
有。早期向量数据库选了Chroma——轻量、Python原生、5分钟上手。数据量到30万条后查询性能断崖下降(>2秒)，因为Chroma的索引是纯内存的，没有磁盘持久化优化。

纠正：迁移到Milvus。写了数据迁移脚本(Chroma→JSON→Milvus bulk_insert)，验证余弦相似度一致性(差异<0.0001)。花了一周，但架构上抽象了VectorStore接口，切换实现类即可，业务代码不改。

教训：选型时不能只看"当前规模"，要看"6个月后的预期规模"。Chroma 10万条内表现完美，但我们的评测数据增长远超预期。

【L3追问】你抽象了VectorStore接口，具体怎么设计的？支持哪些操作？切换成本在哪？
【L3·你的回答】
接口设计：
```python
class BaseVectorStore(ABC):
    @abstractmethod
    async def insert(self, vectors, metadata) -> list[str]: ...  # 返回IDs
    @abstractmethod
    async def search(self, query_vector, top_k, filter_expr) -> list[SearchResult]: ...
    @abstractmethod
    async def delete(self, ids): ...
    @abstractmethod
    async def count(self) -> int: ...

class ChromaStore(BaseVectorStore): ...
class MilvusStore(BaseVectorStore): ...
```

切换成本：只需在DI配置中改一行——`get_vector_store() -> MilvusStore()`。业务代码通过接口调用，完全不感知底层实现。

真正的成本在数据迁移(不是代码层面)——需要确保迁移后向量精度一致、metadata映射正确、索引重建。我们专门写了验证脚本(迁移前后抽样1000条，余弦相似度差异<0.0001才算通过)。

这就是"面向接口编程"的价值——不是过度设计，是真正的架构前瞻性。

【L4追问】如果将来要支持多种向量数据库混合使用(如根据数据量自动路由)，怎么设计？
【L4·你的回答】
在VectorStore上层加路由层：
```python
class VectorStoreRouter:
    def __init__(self, stores: dict[str, BaseVectorStore], router: RouterStrategy):
        self.stores = stores
        self.router = router
    
    async def search(self, query_vector, top_k, filter_expr, collection):
        store = self.router.select(collection)  # 根据collection/数据量/延迟要求选store
        return await store.search(query_vector, top_k, filter_expr)
```

路由策略：
① 按collection——评测数据集A→Milvus(大规模)，数据集B→Chroma(小规模快速迭代)
② 按数据量——<10万条→Chroma(低延迟)，>10万条→Milvus(高吞吐)
③ 按延迟要求——实时查询→Chroma(轻量)，批量评测→Milvus(高性能)

关键：路由层也实现BaseVectorStore接口(装饰器模式)，对上层完全透明。

【L5追问】这种多存储路由方案有什么隐藏问题？数据一致性怎么保证？
【L5·你的回答】
隐藏问题：
① 数据孤岛——同一类数据可能散落在不同Store，跨Store查询需要聚合结果→延迟叠加
② 迁移一致性——数据从Chroma迁移到Milvus过程中，新数据可能写入两边→需要双写+校验
③ 元数据同步——每个Store的filter能力不同(Chroma支持dict filter，Milvus支持标量索引)，路由后filter可能失效

解决方案：
① 尽量避免自动迁移——由管理员手动触发迁移，迁移期间该collection只读
② 双写窗口期——迁移脚本逐批处理(每批1000条)，已迁移的数据从Chroma删除+写入Milvus。窗口期(单批处理时间)极短
③ 元数据Schema统一——在VectorStore接口层定义统一的filter语法(类似MongoDB的查询语法)，各实现类翻译成底层语法

诚实说：我们的规模不需要混合路由。但架构上预留了这个能力——这是"过度设计"和"前瞻性设计"的边界把握。""")

Q("Q12. LangChain vs LlamaIndex，你为什么选LangChain？踩过什么坑？",
"""【L1·你的回答】
选LangChain原因：①Agent框架更成熟(Tool Calling/ReAct/Multi-Agent)；②Chain组合灵活(PromptTemplate→LLM→OutputParser可自由编排)；③生态更大(更多Tool集成/社区/教程)。

LlamaIndex优势在文档解析和索引结构(更好的Chunking策略/树索引/关键词索引)，我们的RAG评测模块参考了它的设计思路。但核心需求是Agent测试编排，LangChain更匹配。

【L2追问】LangChain有什么坑？你在生产环境怎么用的？
【L2·你的回答】
踩过的坑：
① 版本迭代太快——0.x版本API频繁Breaking Change。解决：pip freeze锁定版本，升级前在staging环境验证
② AgentExecutor死循环——默认max_iterations太高(15)，Tool调用失败后Agent反复重试。解决：设max_iterations=5 + early_stopping_method='generate'
③ 序列化问题——Chain对象pickle极不稳定(依赖图复杂)。解决：不存Chain对象，只存配置JSON，运行时动态构建
④ 文档滞后——部分API文档与实际行为不一致。解决：关键逻辑直接读源码(特别是AgentExecutor._call和ToolCallingAgent)
⑤ Callback过于灵活——callback事件太多(几十种)，调试困难。解决：只订阅关键事件(on_llm_start/on_llm_end/on_tool_start/on_tool_end)

生产环境策略：核心评测逻辑自己封装(不依赖LangChain)，Agent测试框架保留LangChain(它的Agent编排确实好用)。关键路径不依赖第三方框架的"魔法"，保持可控性。

【L3追问】AgentExecutor._call的源码执行流程？它怎么处理Tool调用循环的？
【L3·你的回答】
我追踪过关键路径，核心流程：

1. AgentExecutor._call() → 进入迭代循环
2. 每轮迭代：
   a. 调Agent.plan()——将当前状态(输入+历史+中间步骤)构造Prompt→调LLM→解析输出
   b. 如果是AgentAction(需要调Tool)→AgentExecutor._perform_agent_action()
      - 查Tool字典找对应Tool
      - 调Tool.run(tool_input)，捕获异常
      - 结果包装为AgentStep(action, observation)
      - 加入intermediate_steps列表
   c. 如果是AgentFinish(最终答案)→跳出循环，返回结果
3. 循环控制：
   - max_iterations：最大迭代次数，超过后根据early_stopping_method处理
   - early_stopping_method='force'：强制返回当前输出
   - early_stopping_method='generate'：最后一次调LLM要求给出最终答案

死循环根源：LLM返回的Tool参数错误→Tool执行失败→observation是错误信息→LLM根据错误信息再次尝试→参数仍然错误→无限循环。解决：①max_iterations限制；②Tool执行加异常分类(可重试错误vs不可重试)；③自定义callback检测重复调用同一Tool+相同参数

【L4追问】LangChain的RunnableSequence和Chain有什么区别？LCEL是什么？
【L4·你的回答】
LangChain演进：旧Chain(继承Chain类，自定义_call)→新LCEL(LangChain Expression Language，用|管道符组合Runnable)。

旧Chain的问题：①继承式，难组合(不同Chain类型不同基类)；②难以流式(Streaming需要特殊处理)；③难以并行(多个Chain并行执行需要额外编排)

LCEL核心：所有组件都是Runnable(统一接口：invoke/batch/stream/ainvoke/abatch/astream)。用|管道符组合：
```python
chain = prompt | llm | output_parser
# 等价于：RunnableSequence(prompt, llm, output_parser)
```

LCEL优势：
① 自动流式——上游Runnable支持stream→下游自动stream
② 自动并行——batch()自动并行处理多个输入
③ 可观测——自动生成调用链(每个Runnable的输入输出)
④ 类型安全——Pydantic模型贯穿全链路

我们的选择：新功能用LCEL(更简洁)，旧Agent测试保留LangChain AgentExecutor(LCEL的Agent支持还不够成熟)。这是"渐进式迁移"。

【L5追问】LangChain的Callback机制底层怎么实现的？事件怎么传播的？
【L5·你的回答】
Callback机制基于"责任链+观察者"模式：

核心类：
- BaseCallbackHandler：抽象处理器，定义on_llm_start/on_llm_end/on_tool_start等方法
- CallbackManager：管理多个Handler，事件到来时分发给所有Handler
- get_callback_manager()：通过contextvars获取当前上下文的CallbackManager(线程/协程安全)

事件传播流程(以LLM调用为例)：
1. BaseLLM.generate()开始→获取当前CallbackManager→调callback_manager.on_llm_start(serialized, prompts)
2. 如果LLM支持streaming→每次生成token→on_llm_new_token(token)
3. LLM调用结束→on_llm_end(response)
4. 如果出错→on_llm_error(error)

contextvars传递：每个Runnable执行前创建子CallbackManager(通过configure(callbacks))→存到contextvars→子Runnable通过get_callback_manager()获取→自动形成调用链

我们的使用：自定义CallbackHandler收集所有LLM调用和Tool调用的耗时/Token消耗/错误→存入评测结果。这是实现"可观测性"的关键机制。

但Callback的缺点是"侵入式"——需要在每个Runnable调用时传递callbacks参数。如果忘了传，那一段就监控不到。这是我们在Agent测试中踩过的坑。""")

Q("Q13. RAGAS评测框架的指标怎么计算的？和DeepEval对比？",
"""【L1·你的回答】
RAGAS四个核心指标：
① Faithfulness(忠实度)：把答案拆成claims→用LLM判断每个claim是否可由context支持→忠实度=被支持的claims/总claims
② Answer Relevancy(答案相关性)：用LLM根据答案反推问题→计算反推问题与原始问题的语义相似度
③ Context Precision(上下文精确度)：检索到的上下文中，真正有用的比例
④ Context Recall(上下文召回率)：答案中需要的所有信息，有多少在上下文中被检索到了

RAGAS底层用LLM-as-Judge(默认GPT-4)，每个指标有固定的评测Prompt模板。

DeepEval对比：更通用(支持更多指标：偏见/毒性/Hallucination/G-Eval)，CI集成更好，但RAGAS在RAG专用指标上更深入。

【L2追问】Faithfulness拆成claims后怎么判断每个claim？LLM判断可靠吗？
【L2·你的回答】
Faithfulness计算流程：
1. 用LLM把答案拆成原子陈述句(claims)。Prompt："Break the following answer into individual factual claims: {answer}"
2. 对每个claim，用LLM判断："Based on the given context, is the claim '{claim}' supported? Answer YES or NO."
3. Faithfulness = YES的claims数 / 总claims数

LLM判断的可靠性问题：
① 有时候LLM判断"YES"但实际是部分支持(claim是"小明2020年去了北京"，context是"小明2020年去旅行了")→模糊边界
② 负面陈述("小明没有去上海")在context里找不到支持→可能误判为NO(实际是TRUE)

我们的校准方法：
- 每月抽样100条人工标注，和RAGAS评分对比
- 计算Kappa一致性系数，监控偏移
- 如果Kappa<0.6→检查评测Prompt是否需要调整

【L3追问】Answer Relevancy的"反推问题"怎么做的？为什么能衡量相关性？
【L3·你的回答】
Answer Relevancy计算流程：
1. 对于答案中的每个句子，用LLM生成"这个句子在回答什么问题？"→得到一组反推问题
2. 计算每个反推问题和原始问题的语义相似度(用embedding的余弦相似度)
3. Answer Relevancy = 所有反推问题的相似度平均值

直觉：如果答案和问题相关，答案里的每句话应该都在回答原始问题(或其子问题)。反推问题应该和原始问题语义相似。

例子：
- 原始问题："苹果手机电池不耐用怎么办？"
- 答案包含："关闭后台刷新可以省电"→反推问题："怎么省电？"→和原始问题相关(高相似度)
- 答案包含："苹果公司总部在加州"→反推问题："苹果公司总部在哪？"→和原始问题无关(低相似度)→降低Relevancy

但局限：语义相似度不等于真正的相关性。"苹果手机"和"苹果公司"在语义上相关，但对用户来说答案跑了题。这是embedding模型的固有局限。

【L4追问】RAGAS指标之间的关联性？如果Faithfulness高但Answer Relevancy低说明什么？
【L4·你的回答】
指标关联分析：
- Faithfulness高 + Relevancy高 = 最佳(答案相关且不编造)
- Faithfulness高 + Relevancy低 = 答非所问但内容正确(如用户问价格，回答产品功能——功能描述是正确的但没回答价格)
- Faithfulness低 + Relevancy高 = 答案相关但有编造(如用户问价格，回答了一个虚构的价格数字)
- Faithfulness低 + Relevancy低 = 最差(既无关又编造)
- Context Precision高 + Context Recall低 = 检索到的内容都精准但遗漏了重要信息(需要提高检索召回率)
- Context Precision低 + Context Recall高 = 检索到了所有需要的信息但夹杂了大量无关内容(需要提高检索精度)

实际案例：我们的某次评测中，一个Prompt改版后Faithfulness从0.85升到0.92，但Relevancy从0.88降到0.75。分析发现：新Prompt让模型过度保守(只回答context里明确有的)，导致不敢回答context中隐含的信息。调优方向：加指令"利用上下文中的信息，适度推理"。

【L5追问】你提到用Kappa系数做一致性分析。Cohen's Kappa和Fleiss' Kappa有什么区别？RAGAS评测该用哪个？
【L5·你的回答】
Cohen's Kappa：衡量两个评分者之间的一致性。适用于2个评分者对N个样本的二分类/多分类任务。公式：κ = (p_o - p_e) / (1 - p_e)，p_o=观察到的一致率，p_e=随机一致率。

Fleiss' Kappa：Cohen's Kappa的扩展，适用于多个评分者(>2)。衡量K个评分者对N个样本的一致性。

我们的场景用Cohen's Kappa——比较两个"评分者"(RAGAS自动评分 vs 人工评分)对同一批样本的一致性。

具体做法：
① 随机抽100条评测结果
② 人工标注每条的"是否通过"(二元判断：faithfulness≥0.8为通过)
③ RAGAS也按同样阈值判断
④ 计算Cohen's Kappa
⑤ 解释：κ>0.8=几乎完全一致，0.6-0.8=高度一致，0.4-0.6=中度一致，<0.4=低一致

如果κ<0.6：①检查RAGAS的评测Prompt是否合理；②检查人工标注标准是否清晰(人工标注也需要一致性校验)；③考虑调整阈值或引入更多维度。

注意：Kappa的局限性——受样本分布影响(如果大部分样本都通过或都不通过，p_e会很高，κ会偏低)。需要确保样本的通过/不通过比例合理(不要全通过或全不通过)。""")

Q("Q14. 为什么用Milvus？Pinecone和Qdrant各有什么优劣？",
"""【L1·你的回答】
选Milvus原因：
① 多种索引类型——IVF_FLAT(省内存)/HNSW(高精度)/DiskANN(磁盘索引，超大规模)
② 混合查询——标量过滤+向量检索，一条语句搞定(如"找faithfulness<0.7且语义相似的case")
③ 云原生架构——存算分离(可扩展)，但我们用的standalone模式(单机够用)
④ 社区活跃——中文社区大，文档完善

对比：Pinecone(SaaS，不用运维但数据安全风险+成本高)、Qdrant(不错但社区比Milvus小)、Weaviate(自带向量化但重)

【L2追问】Pinecone和Milvus的性能对比？什么场景该用Pinecone？
【L2·你的回答】
性能：
- Pinecone：基于K8s的托管服务，自动扩缩容，p95延迟<100ms(pod-based架构)
- Milvus standalone：单机部署，HNSW索引下p95延迟<10ms(数据在本地)
- Milvus cluster：分布式部署，水平扩展，和Pinecone同级别性能

Pinecone适用场景：
① 不想管基础设施的团队——开箱即用，零运维
② 弹性需求大——流量波动大(如电商大促)，自动扩缩容
③ 多租户——内置namespace隔离

不适用场景(我们的情况)：
① 数据安全合规——评测数据含敏感用例，不想出内网
② 成本——Pinecone按Pod×小时计费，我们的评测量大(24小时跑)，自建更便宜
③ 定制化——需要和PostgreSQL深度集成(JOIN查询)，Pinecone是黑盒

【L3追问】Qdrant的量化索引(Scalar Quantization/Product Quantization)是什么？什么场景用？
【L3·你的回答】
Qdrant的两种量化方案：

Scalar Quantization(SQ)：把float32→uint8(每个维度)。scale = (max-min)/255。内存减少4倍，精度损失极小(因为向量维度间相对关系保留)。适合：内存紧张但精度要求高的场景。

Product Quantization(PQ)：把向量切分成M个子段，每段用K-Means聚类(生成码本)。向量→M个码本索引。内存减少极多(如128维→8段×1byte=8bytes，原始512bytes)，但精度损失较大。适合：超大规模(亿级)+精度要求不极端的场景。

选择策略：
- 百万级 + 高精度 → SQ(4x压缩，几乎无损)
- 亿级 + 可接受精度损失 → PQ(64x压缩)
- 十万级 + 极致精度 → 不量化(FP32全精度)

我们的场景(几十万向量)：Milvus HNSW + FP32全精度，不量化。内存够用，不需要牺牲精度。

【L4追问】Milvus的DiskANN索引是什么？和HNSW在磁盘场景下有什么区别？
【L4·你的回答】
DiskANN(Microsoft Research)：专为磁盘场景设计的ANN索引。

HNSW的问题：图结构需要全在内存中，数据量大→内存放不下→换到磁盘→随机IO(图遍历)性能崩塌。

DiskANN的创新：
① Vamana图——建图时优先选"长边"(连接远距离节点)，减少图直径。查询时更少跳数→更少磁盘IO
② 向量压缩——图结构在内存(SSD缓存)+原始向量在SSD(按需加载)。查询时：内存中图遍历→确定候选节点→按需从SSD加载候选节点的完整向量→精排
③ 两阶段搜索——粗筛(内存图遍历+压缩向量)→精排(SSD加载原始向量)

适用场景：向量量极大(十亿级)，内存放不下全量索引，但SSD容量够。性能：比纯内存HNSW慢但比全SSD方案快很多。

我们的场景不需要DiskANN(几十万向量，内存足够)。但架构上知道这个选项——如果将来数据量暴增，Milvus支持无缝切换索引类型。

【L5追问】如果向量量到10亿级别，单机Milvus撑不住，分布式方案怎么设计？
【L5·你的回答】
Milvus分布式架构(Milvus Cluster)：

① 存储层分离：
- Root Coord：管理DDL(创建/删除Collection)
- Data Coord：管理数据段(segment)分配
- Index Coord：管理索引构建任务
- Query Coord：管理查询调度

② 计算层分离：
- Data Node：存储原始数据(持久化到MinIO/S3)
- Index Node：构建索引(计算密集)
- Query Node：执行查询(加载索引到内存)

③ 数据分片(Sharding)：
- 按collection分片(shard_num=N)，每个shard由不同Query Node处理
- 查询时：Query Coord广播到所有Query Node→各Node在自己的shard搜索→合并结果(Top-K归并)

④ 动态伸缩：
- 数据增长→加Data Node(存储)
- 查询量增长→加Query Node(计算)
- 索引构建加速→加Index Node

我们的演进路径：当前Milvus Standalone(几十万)→如果到千万级→加内存升级机器→如果到亿级→迁移到Milvus Cluster。架构设计预留了切换能力(通过BaseVectorStore接口)。""")

Q("Q15. 模型API怎么选？为什么用GPT-4做Judge？多模型成本控制？",
"""【L1·你的回答】
按场景选模型：
① 评测Judge：GPT-4(推理能力最强，RAGAS官方推荐，Judge准确性直接影响评测可靠性)
② 日常对话测试：GPT-4o-mini(性价比高，1/10价格)
③ 代码生成测试：DeepSeek-V3(代码能力出色+成本低)
④ 中文场景：Qwen(中文理解好，成本低)
⑤ 本地部署：vLLM部署开源模型(高频+敏感场景)

多模型路由：配置文件定义场景→模型映射，LLMClientFactory动态选择

【L2追问】多模型成本怎么控制？会不会账单爆炸？
【L2·你的回答】
分层控制：
① 评测Judge(GPT-4)最贵(约$30/1M tokens)→限制并发(评测任务排队，最多3个并发Judge调用)，设置月度预算告警
② 日常测试用GPT-4o-mini(约$0.15/1M tokens)→量大面广，不限制
③ 本地模型(vLLM)→高频+敏感场景，只需GPU电费

Token预算管理：
- 每个评测任务设定max_tokens上限(根据测试集大小估算)
- Grafana看板：每日Token消耗趋势+模型维度拆解
- 月度预算告警：消耗达80%→企业微信告警，达100%→自动切换为本地模型

成本对比：全用GPT-4(日均1000次评测×5000 tokens)→月费$4500。分层后(5%GPT-4 + 60%GPT-4o-mini + 35%本地)→月费约$400，节省90%。

【L3追问】本地部署vLLM的GPU成本怎么算？和API调用的盈亏平衡点在哪？
【L3·你的回答】
盈亏平衡计算：

API方案(GPT-4o-mini)：$0.15/1M input + $0.60/1M output tokens
- 日均100万tokens → 约$30/天 → $900/月

自建方案(A10 GPU云服务器)：
- A10(24GB)云租赁约$0.8/小时 → $576/月(24×30)
- 一张A10可跑7B模型(Qwen-7B)，吞吐约2000 tokens/s
- 日均100万tokens → 约500秒(8分钟)GPU时间 → 实际利用率很低(大部分时间闲置)

盈亏平衡：日均约1900万tokens时自建=API成本($576/月=$0.3/百万tokens×1900万/100万)。但我们日均远不到1900万。

结论：当前规模用API更划算。但架构上预留了本地模型接入点——不是为了省钱，是为了数据安全(敏感评测数据不出内网)和延迟可控(API有排队风险)。

【L4追问】vLLM的PagedAttention吞吐优化具体怎么实现的？Continuous Batching是什么？
【L4·你的回答】
PagedAttention(已在Q130讲)核心是KV Cache的分页管理。

Continuous Batching(vLLM的核心吞吐优化)：
传统Batching：一批请求必须同时到达→同时推理→等最慢的完成→才能处理下一批。短序列被长序列拖累(木桶效应)。

Continuous Batching：请求不等批，动态加入和离开：
① 请求队列持续接收新请求
② 每步推理时：当前活跃请求(已完成部分+新加入)组成batch→一起推理
③ 某个请求生成完(EOS/达到max_tokens)→从batch移除
④ 新请求→立即加入下一轮batch

效果：GPU利用率大幅提升(不再等慢请求)。实测吞吐量提升2-10倍(取决于请求长度分布)。

类比：传统Batching=固定班车(必须等满才发车)，Continuous Batching=流水线(来一个处理一个)。

【L5追问】vLLM的调度策略(Scheduling Policy)有哪些？怎么选？
【L5·你的回答】
vLLM支持多种调度策略：
① FCFS(First Come First Served)——先到先服务，最公平但吞吐不是最优
② Priority——按优先级调度(如评测Judge任务优先级高于日常测试)
③ Preemption——高优先级请求到达时，抢占低优先级请求的KV Cache(存到CPU内存，GPU释放)

抢占策略：
- Swap：低优请求的KV Cache从GPU→CPU内存，GPU释放后给高优请求。高优完成后Swap回来。代价：Swap耗时(取决于序列长度)
- Recompute：直接丢弃低优请求的KV Cache，GPU释放给高优。高优完成后重新计算低优请求。代价：重新计算(比Swap快当序列短时)

我们的配置：评测场景请求长度相近(都几千tokens)，FCFS+Continuous Batching够用。如果有实时和批量的混合场景，才需要Priority调度。""")

print(f"[OK] 1.2节完成 (Q11-Q15)")

# ============ 1.3 项目难点与踩坑经验（Q16-Q25）============
S("1.3 项目难点与踩坑经验（Q16-Q25）")

Q("Q16. 项目中遇到最大的技术难点是什么？怎么解决的？",
"""【L1·你的回答】
最大的难点是"LLM输出的不确定性"——同一个Prompt、同一份数据、同一个模型，两次调用结果可能不同。传统软件测试的核心假设是"确定性"(相同输入→相同输出)，但AI测试完全打破了这个假设。

解决思路：从"验证单次输出"转为"统计多次输出的质量分布"。核心改动：①每个评测case至少跑3次，取平均值和标准差；②引入"稳定性"指标(多次运行的指标方差)；③报告不仅展示"通过率"，还展示"置信区间"(如faithfulness=0.85±0.03)。

【L2追问】跑3次成本翻3倍，怎么权衡？有没有更高效的方案？
【L2·你的回答】
渐进策略：
① 关键case跑3次(如安全相关、合规相关)——这些不能容忍不确定性
② 一般case跑1次——如果指标在正常范围(和baseline差异<5%)，不追加
③ 异常case自动追加——第1次结果异常(和baseline差异>10%)→自动再跑2次→看是偶发波动还是真的退化

效率提升：
- 设置Temperature=0(或极低)减少随机性——但注意T=0不能完全消除非确定性(因为GPU浮点运算的非确定性)
- 固定random seed——如果模型API支持(多数不支持，OpenAI的seed参数是best-effort)
- 用多个Judge交叉验证替代多次生成——一次生成+3个Judge打分，比3次生成+1个Judge更高效(但评估维度不同)

成本权衡：安全case多跑几次是值得的(成本vs风险)，一般case单次够用。这是"风险导向的测试策略"。

【L3追问】GPU浮点运算为什么是非确定性的？和CPU有什么不同？
【L3·你的回答】
GPU浮点非确定性来源：
① 并行归约(Reduction)——多个线程并行计算softmax的sum，归约顺序不同→浮点累加顺序不同→舍入误差不同→最终结果微小差异
② cuBLAS/cuDNN内部实现——不同的算法选择(如GEMM的tiling策略)可能导致不同计算顺序
③ 非确定性算子——某些cuDNN操作的deterministic模式默认关闭(因为性能差)，需要显式开启torch.backends.cudnn.deterministic=True

CPU相对确定：因为单线程顺序执行，浮点累加顺序固定。但多线程CPU也有类似问题。

这就是为什么即使Temperature=0，LLM输出也可能有微小差异——差异通常不影响语义(只是概率分布上小数点后第3-4位的变化)，但偶尔可能影响Token选择(两个Token概率极其接近时)。

对测试的影响：不能期待"100%可复现"，只能期待"统计上一致"。这是AI测试和传统测试最根本的哲学差异。

【L4追问】"统计上一致"怎么量化？什么阈值算"一致"？
【L4·你的回答】
量化方法：
① 多次运行的指标均值和标准差——均值反映"典型表现"，标准差反映"稳定性"。如果均值变化<2%且标准差<0.05，认为"一致"
② 效应量(Effect Size)——Cohen's d = (mean1 - mean2) / pooled_std。d<0.2=微小差异(可忽略)，0.2-0.5=小差异，>0.8=大差异
③ Bootstrap置信区间——对多次运行结果重采样1000次，计算95%置信区间。两个版本的置信区间有重叠→差异不显著

阈值设定需和业务方对齐：
- 安全类指标：不允许任何退化，阈值极严格
- 体验类指标：<3%变化可接受
- 新功能上线：<5%退化可接受(因为新功能可能带来其他提升)

关键是：不是给一个固定数字，而是给一个"风险可控的范围"。

【L5追问】如果两个Prompt版本的faithfulness从0.85降到0.82(下降3.5%)，但标准差从0.03增大到0.08，你怎么判断？
【L5·你的回答】
这是典型的"均值vs方差"权衡问题。需要深入分析：

① 首先看原始数据分布——画箱线图(boxplot)。如果方差增大是因为少数case表现极差(离群值)→针对性修复那几个case即可，不是Prompt整体问题
② 分难度看——按case难度分组(简单/中等/困难)，看每组的均值变化。如果简单case不变、困难case大幅下降→Prompt对复杂场景变差了
③ 统计检验——Welch's t-test(不假设等方差)检验均值差异是否显著。p<0.05→差异显著，需要关注
④ 业务判断——如果faithfulness 0.82仍在业务可接受范围内(如阈值是0.8)，且方差增大不带来极端失败case→可以接受

最终建议给业务方：faithfulness微降但仍在阈值内，但稳定性变差(标准差0.03→0.08)。建议：①排查离群case是否可修复；②如果离群case是罕见场景→可接受；③如果离群case是常见场景→需要回滚或修复。

核心能力不是"给数字"，而是"解读数字背后的含义并给出可操作的结论"。这是AI测试工程师和传统测试工程师的关键区别。""")

Q("Q17. API限流(Rate Limiting)问题怎么处理的？踩过什么坑？",
"""【L1·你的回答】
多模型API都有Rate Limit(如OpenAI的RPM/TPM限制)。我们的处理：

① 客户端限流——token-bucket算法，控制每秒请求数不超过API限制
② 队列缓冲——超过限流的请求进入Redis队列，排队等待
③ 退避重试——遇到429(Too Many Requests)，指数退避+Retry-After header
④ 多Key轮换——多个API Key轮流使用(不同Key有独立限额)

踩坑：OpenAI的Rate Limit分RPM(Requests Per Minute)和TPM(Tokens Per Minute)，只关注RPM而忽略TPM→大请求被限流。解决：根据预估Token消耗动态调整请求频率。

【L2追问】Token Bucket算法具体怎么实现的？和Leaky Bucket、滑动窗口有什么区别？
【L2·你的回答】
Token Bucket(令牌桶)：
- 固定速率生成Token(如10 token/s)→桶容量上限(如100 token)
- 请求到来→需要从桶中取N个token→够则放行(桶减少N)→不够则拒绝/等待
- 优点：允许突发流量(桶里有积累的token)→平滑限流
- 实现：Redis存储(last_refill_time, current_tokens)，每次请求计算应该补充的token数

Leaky Bucket(漏桶)：
- 请求进入桶(排队)→固定速率"漏出"(处理)
- 桶满了→拒绝请求
- 优点：输出速率绝对平滑；缺点：不允许突发

滑动窗口(Sliding Window)：
- 维护过去1分钟的时间戳列表
- 新请求→删除1分钟前的时间戳→计数→超过限制则拒绝
- 优点：精确(不像固定窗口的边界问题)；缺点：内存开销大(存时间戳)

我们的选择：Token Bucket(允许突发，评测任务特点是"间歇性突发"——提交任务时请求多，执行时请求少)。用Redis Lua脚本保证原子性。

【L3追问】Redis Lua脚本怎么做原子性Token Bucket？多Key轮换怎么实现？
【L3·你的回答】
Lua脚本(保证检查+扣减原子)：
```lua
local key = KEYS[1]  -- bucket key
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])  -- tokens per second
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- 补充token
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * rate)
last_refill = now

-- 判断
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, 60)
    return 1  -- 放行
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    return 0  -- 拒绝
end
```

多Key轮换：
```python
class APIKeyRotator:
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.idx = 0  # Round-Robin
    
    def get_key(self):
        key = self.keys[self.idx]
        self.idx = (self.idx + 1) % len(self.keys)
        return key
```

配合：每个Key有独立的Token Bucket(Redis key=rate_limit:{api_key})。选择Key时不仅Round-Robin，还检查该Key的bucket是否有token→没有则跳过选下一个。

【L4追问】如果所有Key都限流了(全用完配额)，怎么优雅降级？
【L4·你的回答】
降级策略(按优先级)：

① 等待重试——最优雅，排队等待(指数退避+Retry-After)，适合非实时场景
② 切备用模型——GPT-4限流→自动切GPT-4o-mini(便宜但推理能力弱)→Judge准确性可能下降但至少不中断
③ 降级到本地模型——如果本地部署了vLLM，切换到本地模型(无API限流但能力可能弱)
④ 优先级排队——评测Judge任务(必须高精度)→优先分配配额，日常测试→降级等待
⑤ 任务延期——标记任务为"rate_limited"，定时任务稍后重试。前端展示"等待API配额中..."

我们的实践：评测Judge用GPT-4(不可降级，必须等配额)，日常测试降级到GPT-4o-mini或本地模型。不同优先级的任务用不同队列，保证核心任务不受影响。

【L5追问】如果API突然改了Rate Limit策略(如从RPM改为TPM)，你的系统怎么自适应？
【L5·你的回答】
无法完全自适应，但可以通过监控+配置化减少影响：

① 配置驱动——Rate Limit参数(RPM/TPM/并发数)存配置文件而非硬编码，改配置即可调整
② 监控反馈——记录每个API请求的响应(成功/429/其他错误)。如果429比例突增→自动调低限流阈值(保守策略)
③ 动态调整——定期(每分钟)分析过去5分钟的429率：
   - 429率>5%→当前限流阈值降低20%
   - 429率<0.1%→当前限流阈值提高10%(试探上限)
④ 告警——429率突增→企业微信告警→人工介入

但诚实说：完全自适应很难。API的Rate Limit策略变化可能是隐式的(如GPT-4的TPM从100K降到80K)，需要依赖API文档更新或主动压测发现。我们的策略是"防御性编程"——留20%的buffer(设置阈值=官方限额×0.8)，避免打满配额。""")

print(f"[OK] 1.3节部分完成 (Q16-Q17)，继续追加...")


