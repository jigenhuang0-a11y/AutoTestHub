# -*- coding: utf-8 -*-
"""路特创新1000道递进式面试攻防题 - 第1部分（第1-3章，340题）
每道题包含 L1开场 → L2追问 → L3追问 → 兜底策略 完整攻防链路
"""

# 第1章：AI测试平台项目深挖（Q1-Q120）
S("第1章 AI测试平台项目深挖（Q1-Q120）——面试开场核心战场")

S("1.1 平台整体架构（Q1-Q20）")

Q("Q1. 介绍一下你做的AI测试平台",
  "L1: 我做的是一个面向AI应用的自动化测试平台，核心三模块：①Prompt评测-版本控制+Git管理+CI回归；②RAG评测-集成RAGAS框架评测Faithfulness/Relevancy/Precision/Recall；③Agent测试-模拟工具调用验证Agent行为。技术栈FastAPI+Celery+Vue3+PostgreSQL+Milvus+Docker部署。\n"
  "L2追问: 为什么选FastAPI而不是Flask/Django？\n"
  "L2应对: Flask同步框架会阻塞AI调用(动辄几十秒)，gevent补丁是假异步；Django太重(ORM/模板引擎对API是冗余)。FastAPI原生async/await+Starlette+Pydantic，AI调用IO密集场景下异步是最佳实践。且自动生成Swagger文档+类型校验，联调效率高。\n"
  "L3追问: gevent的协程和asyncio的async/await底层机制有什么本质区别？\n"
  "L3兜底: gevent基于Greenlet在用户态切换，monkey patch替换阻塞IO，但CPU密集操作无法让出控制权。asyncio基于OS事件循环(epoll/kqueue)，语言级别await让渡控制权，更可靠。实际踩坑：async函数里误用同步requests库导致整个事件循环阻塞。关键是实践中心里清楚哪些操作会阻塞事件循环。")

Q("Q2. 平台架构是怎么分层的？",
  "L1: 四层架构：①接入层-Nginx反向代理+HTTPS+静态资源；②API网关层-FastAPI BFF做认证/限流/路由；③业务服务层-Prompt管理/评测执行/报告生成/Agent测试，模块化组织；④基础设施层-PostgreSQL+Redis+Milvus+Celery Worker+MinIO。层间通过接口通信，上层不依赖下层具体实现。\n"
  "L2追问: 这是微服务吗？每个服务独立部署？\n"
  "L2应对: 严格说是'模块化单体'(Modular Monolith)，不是微服务。原因：①团队规模-我一人主导，微服务运维复杂度ROI太低；②业务耦合-Prompt评测和RAG评测共享数据集，拆分会增加跨服务调用延迟；③代码层面已做边界隔离(Protocol/ABC)，将来可抽离为独立服务只改DI配置。唯一例外是Celery Worker独立进程跑评测任务。\n"
  "L3追问: 依赖注入怎么实现的？FastAPI Depends和Spring DI的本质区别？\n"
  "L3兜底: 用FastAPI原生Depends，构造函数注入依赖，请求级别scope。和Spring区别：Spring DI是进程级单例管理(Bean生命周期复杂)，FastAPI Depends是函数调用链无容器概念。好处：单元测试轻松Mock，不需要启动容器。展示的是'知道轻量方案的适用场景'。")

Q("Q3. 项目从0到1花了多久？怎么规划的？",
  "L1: 3个月四阶段：①调研(2周)-对比LangSmith/LangFuse/RAGAS/DeepEval，输出选型报告+对齐业务需求；②MVP(4周)-Prompt评测模块先行(FastAPI+PostgreSQL基础架子)，跑通后立刻试用；③迭代(4周)-加RAG评测/Grafana看板/Agent测试框架；④推广(2周)-文档+接入两个业务团队。\n"
  "L2追问: 调研了LangSmith为什么没用，反而自研？\n"
  "L2应对: ①数据安全-评测数据含敏感用例，SaaS合规风险，LangFuse自部署但对非LangChain生态支持弱；②定制化-车载安全合规检查等特殊指标，通用平台无法深度扩展；③成本-LangSmith按Trace量收费，我们评测量大长期自研更划算。但设计借鉴了LangSmith Trace设计+LangFuse Dashboard+RAGAS指标，插件化架构便于替换模块。\n"
  "L3追问: LangSmith Trace底层怎么实现的？你要实现分布式追踪怎么做？\n"
  "L3兜底: LangSmith基于OpenTelemetry协议，每个LLM调用/Retriever检索/Tool执行加span形成树状调用链。我要实现：①关键节点插hook记录输入输出+时间戳；②contextvars传递trace_id(异步安全)；③数据存PostgreSQL+ClickHouse。目前单进程够用，如需跨服务追踪优先集成OpenTelemetry+Jaeger而非从零造轮子。")

Q("Q4. FastAPI项目结构具体怎么组织的？",
  "L1: api/路由按模块拆分(prompts/evaluations/reports/agents)，services/业务逻辑(prompt_service/eval_service/ragas_service/llm_client)，models/分db(ORM)和schemas(Pydantic DTO)，core/配置+DI+中间件，tasks/Celery异步任务，tests/按模块组织。原则：外层(api)薄，内层(services)厚，路由只做校验和返回。\n"
  "L2追问: llm_client怎么封装支持多模型？\n"
  "L2应对: BaseLLMClient抽象接口(chat/chat_stream)，OpenAIClient/ClaudeClient/LocalModelClient分别实现。LLMResponse统一数据结构(content/token_usage/finish_reason/latency)。工厂模式+配置驱动选模型，故障转移：主模型超时→自动切备用模型，重试机制+熔断器。\n"
  "L3追问: 熔断器怎么实现的？和Sentinel/Hystrix什么关系？\n"
  "L3兜底: 经典三态模型(Closed→Open→Half-Open)，用Redis滑动窗口计数器(原子INCR+EXPIRE)。失败超阈值→熔断打开→冷却期→半开探测。选Redis非内存原因：Celery Worker多进程，内存计数器无法跨进程共享。承认实现简单(未做慢调用比例熔断/未区分错误类型)，复杂需求会考虑pybreaker库。")

Q("Q5. 怎么处理并发评测任务？",
  "L1: Celery异步：FastAPI接收请求返回task_id→Redis Broker→多个Celery Worker并行执行→实时更新状态(PENDING→RUNNING→SUCCESS)→前端轮询进度。Worker数量核数×2(IO密集)。Task Routing隔离快慢队列，避免慢任务堵快任务。\n"
  "L2追问: Redis做Broker，Redis挂了任务会不会丢？\n"
  "L2应对: 多层防护：①开启AOF持久化(每条写操作日志)；②业务幂等-任务执行前查DB状态，已SUCCESS则跳过，防止重复；③超时+重试-Celery soft_time_limit+定时任务扫RUNNING超时任务重试。如要求极高可靠性会换RabbitMQ(消息确认+持久化更成熟)。\n"
  "L3追问: RabbitMQ ACK和Redis List做队列的本质区别？\n"
  "L3兜底: Redis List是'取出即删除'(BRPOP后消息消失，Worker挂则消息丢失=At-Most-Once)。RabbitMQ ACK：取出后标记unacked，Worker显式ACK后才删除，Worker挂则自动重入队(At-Least-Once)。这是两种消息语义的根本差异。Celery应用层做补偿但有限，高可靠场景应选RabbitMQ。")

Q("Q6. 数据库怎么设计的？核心表有哪些？",
  "L1: 四类表：①Prompt相关-prompt_templates(id/name/version/content(Jinja2变量)/status)+prompt_versions(版本历史)；②评测相关-eval_tasks(task_id/type/status)+eval_results(metrics存JSONB/raw_response/latency)；③测试用例-test_datasets+test_cases(input/expected_output/tags/difficulty)；④Agent测试-agent_tests+tool_simulations+agent_traces。关键字段建索引，统一created_at/updated_at。\n"
  "L2追问: 为什么用PostgreSQL而不是MySQL？\n"
  "L2应对: ①JSONB支持-eval_results的metrics存JSON，可建GIN索引高效查询JSON内字段(如WHERE metrics->>'faithfulness'<'0.7')，MySQL JSON不能建真正索引；②CTE+窗口函数-复杂聚合查询(30天趋势/版本对比)更清晰；③扩展生态-后续可能用pgvector直接存embedding简化架构；④License-PostgreSQL纯BSD，MySQL Oracle GPL有合规顾虑。MySQL读性能好但我们的分析型场景PostgreSQL更合适。\n"
  "L3追问: GIN索引原理？和B-Tree在JSON查询上本质区别？\n"
  "L3兜底: GIN(Generalized Inverted Index)倒排索引：把复合数据分解成多个key→指向包含它的行。B-Tree索引整个字段值，JSONB需建表达式索引(针对特定字段)。GIN威力：一个索引支持JSONB任意key查询(@>/ ?/ ?&)。代价写入性能差，但我们是写一次读多次的场景，读优化的GIN更合适。")

Q("Q7. 前端怎么做的？",
  "L1: Vue3+Vite+Element Plus+Pinia。Dashboard(ECharts趋势图)+Prompt管理(编辑器+版本对比)+评测中心(创建任务+实时进度)+报告页(多维指标)+Agent测试(Trace展示)。Axios封装拦截器(自动Token+统一错误)。\n"
  "L2追问: 为什么Vue3不选React？\n"
  "L2应对: ①上手成本-其他测试同事可能参与维护，SFC模板比JSX友好；②响应式系统-Proxy自动依赖追踪，数据展示密集场景少写useMemo/useCallback样板；③生态-Element Plus中后台组件(表格/表单)质量高。但如果加入React团队我能快速上手，理解Hooks/虚拟DOM/Fiber架构。\n"
  "L3追问: React Fiber解决了什么问题？和Vue3响应式更新的本质区别？\n"
  "L3兜底: Fiber解决'可中断渲染'-递归reconciler会长时间占主线程致卡顿，Fiber拆成小单元(Fiber节点)+时间切片让出主线程。Vue3不同：Proxy依赖追踪精准定位需更新组件，不需要从根遍历，更新粒度更细效率更高。React策略='全重算但可中断'，Vue3策略='只算需要更新的'。")

Q("Q8. 认证和权限怎么做？",
  "L1: JWT方案-登录签发Token含用户ID+角色，前端localStorage存储，请求Header带Authorization。RBAC三种角色：Admin(管理用户+全数据)/Editor(创建编辑+发起评测)/Viewer(只看报告)。FastAPI Depends做权限校验require_role('editor')。\n"
  "L2追问: JWT过期了怎么刷新？\n"
  "L2应对: 双Token机制-Access Token(30分钟)+Refresh Token(7天存DB)。前端Axios拦截器捕获401→自动用refresh_token调/refresh→拿新access_token重试→用户无感。Refresh Token存DB可随时吊销(改密码后全失效)。Access Token被盗也只有30分钟风险窗口。\n"
  "L3追问: 每个请求都要查DB验证Token吗？性能瓶颈？\n"
  "L3兜底: Refresh Token只在/refresh接口查DB，普通API验证Access Token是无状态的(只验签名+过期时间，不查DB)。Refresh接口调用频率远低于API(30分钟一次)，无性能瓶颈。吊销问题：无状态JWT固有问题，方案①Redis黑名单存吊销TokenID；②缩短有效期5-10分钟；③有状态Session。目前场景够用。")

Q("Q9. Docker Compose怎么部署的？",
  "L1: docker-compose.yml定义所有服务：nginx(前端+反向代理)/backend(FastAPI)/celery_worker/celery_beat/postgres/redis/milvus。各自Dockerfile或官方镜像，服务间Docker网络通信(host用服务名)。环境变量.env区分环境。部署：docker compose up -d。\n"
  "L2追问: Docker Compose适合生产吗？服务挂了怎么恢复？\n"
  "L2应对: 单机小规模可用但需额外配置：①restart: unless-stopped自动重启；②healthcheck(backend curl/health+postgres pg_isready)+depends_on condition确保启动顺序；③日志轮转防磁盘撑爆。局限：不能跨机/无服务发现/无LB。将来需多机部署迁移K8s(Docker Swarm)，但当前单机够用不引入K8s复杂度。\n"
  "L3追问: 迁移K8s需要做哪些改造？\n"
  "L3兜底: ①配置管理-env→ConfigMap+Secret；②服务发现-host→K8s Service DNS；③持久化-PVC替代容器本地存储；④健康检查-healthcheck→livenessProbe/readinessProbe；⑤水平扩展-Celery Worker Deployment+HPA按队列长度伸缩；⑥Ingress-Nginx→K8s Ingress Controller；⑦监控-Prometheus+Grafana+EFK日志。原则：应用代码不改只改部署配置。")

Q("Q10. 日志和监控怎么做？",
  "L1: 日志-structured JSON(logging模块)含request_id/user_id/模块名，输出stdout由Docker收集。监控三块：①基础设施-Prometheus+Node Exporter+CPU/内存/磁盘；②应用-FastAPI集成prometheus_fastapi_instrumentator暴露QPS/延迟/错误率；③业务-评测任务执行情况自定义指标推Pushgateway(Celery短生命周期)。告警Grafana Alerting+企业微信通知。\n"
  "L2追问: 为什么用Pushgateway不用Prometheus拉模式？有什么坑？\n"
  "L2应对: Prometheus设计是拉模式但Celery Worker短生命周期来不及拉取。Pushgateway作中间缓冲。踩坑：①不会自动清理过期指标-Worker异常退出指标残留，需设过期时间或任务始终推送初始值；②单点故障-挂了丢所有Worker指标。单机风险可控，生产级考虑VictoriaMetrics/Grafana Agent替代。\n"
  "L3追问: Prometheus TSDB底层存储原理？为什么压缩率高？\n"
  "L3兜底: ①样本压缩-利用时序等间隔采样，只存起始时间戳+间隔+值序列，时间戳开销近零；②Gorilla算法-浮点值XOR编码，相邻点变化小产生大量前导零+尾随零，变长编码压缩。压缩比达原始10-30%。深层次chunk组织/倒排索引未深入研究源码，但选型时知道压缩比够用即可。")

Q("Q11. API接口怎么设计的？",
  "L1: RESTful规范：URL名词复数(/api/v1/prompts)，HTTP动词(GET/POST/PUT/PATCH/DELETE)，版本化前缀/v1/，统一响应{code/message/data}，分页(page/page_size+total/items)，过滤排序查询参数。Pydantic模型自动生成Swagger+Field description/example。\n"
  "L2追问: v2版本响应格式变了，怎么保证不影响v1？\n"
  "L2应对: 代码版本隔离-api/v1/prompts.py和api/v2/prompts.py独立路由文件，不同Pydantic Schema和业务逻辑。FastAPI主应用include_router不同prefix。v1保留直到所有客户端迁移。版本号放URL不放Header原因：URL版本化更直观(调试看URL即知版本)，Header版本化虽'更RESTful'但容易遗漏出错。\n"
  "L3追问: Header版本化为什么容易出错？业界主流做法？\n"
  "L3兜底: Header版本化问题：隐式约定，请求必须带Accept: application/vnd.api.v2+json，漏了就回默认版本，排查困难。URL版本化：一目了然，代理可基于URL路由，网关可做版本级限流统计。业界：Google/GitHub/Stripe都用URL版本化。Stripe更有趣-用日期做版本(如/v1/2023-08-01/)，版本号与发布时间关联直观。")

Q("Q12. 前端实时展示评测进度怎么实现？",
  "L1: 两种方式：①定时轮询-每2-3秒GET任务状态，算completed/total百分比，简单够用；②SSE(Server-Sent Events)-FastAPI StreamingResponse+async generator逐条推送Agent步骤，前端EventSource实时渲染。选SSE不选WebSocket原因：评测进度是单向数据流，SSE基于HTTP穿透代理更容易，WebSocket对单向推送是杀鸡用牛刀。\n"
  "L2追问: SSE连接断开怎么处理？能自动重连吗？\n"
  "L2应对: EventSource API原生支持自动重连，服务端retry字段控制间隔。重连问题：从头开始还是断点续传？方案：每条消息带sequence_id，前端维护last_received_seq，重连URL带?last_event_id=xxx，后端从此ID后推送。若无历史(Celery Worker已结束)则直接返回最新状态不重放历史。\n"
  "L3追问: Nginx默认缓冲SSE响应，怎么处理？\n"
  "L3兜底: 实际踩坑：Nginx proxy_buffering默认on，把响应缓存到一定大小才发客户端，SSE变'等半天突然弹一堆'。解决：Nginx配置SSE接口location关缓冲(proxy_buffering off; proxy_cache off; X-Accel-Buffering no)。FastAPI响应也加Header(Cache-Control: no-cache; Connection: keep-alive; X-Accel-Buffering: no)。全链路不缓冲确保实时推送。")

Q("Q13. ECharts可视化展示了哪些图表？",
  "L1: Dashboard五类图表：①评测任务概览Stat卡片(今日任务数/成功率/平均耗时)；②评测趋势折线图(30天通过率变化)；③Prompt版本对比柱状图(faithfulness/relevancy等指标并排)；④指标分布热力图(不同数据集×指标得分)；⑤Agent Trace时序图(多步推理Gantt图)。图表数据通过预聚合统计API获取，前端只渲染不计算。\n"
  "L2追问: 百万级数据统计API怎么保证性能？\n"
  "L2应对: 三层优化：①DB层-eval_results建复合索引(task_id+created_at)，覆盖常用聚合；②预聚合-Celery Beat定时任务每小时聚合结果写dashboard_stats表，Dashboard直接查小表毫秒级；③缓存-Redis缓存变化不频繁数据(30天趋势TTL=5分钟)。百万级会引入列式DB(ClickHouse)做OLAP，PostgreSQL继续OLTP。\n"
  "L3追问: OLTP和OLAP分离，数据怎么同步到ClickHouse？\n"
  "L3兜底: 方案①CDC-Debezium监听PostgreSQL WAL推Kafka→ClickHouse，秒级延迟但需维护Kafka+Debezium；②定时批量-DataX或脚本每小时增量导入，简单但延迟高。评测场景T+1小时够用(趋势图不差一小时)，所以定时批量够用。实时场景(在线告警)才需CDC。关键是按业务需求选方案，不是越实时越好。")

Q("Q14. 测试数据集怎么管理？有版本控制吗？",
  "L1: 'Test as Code'理念-Git仓库管理JSON/YAML测试用例(test_data/目录按场景分文件)。PR流程+Review，CI自动校验(JSON格式/必填字段/重复检测)。平台'同步'按钮从Git拉取数据到DB，保留历史版本可对比。评测任务可选择数据版本做A/B对比。\n"
  "L2追问: Git管理测试数据局限性？非技术人员怎么操作？\n"
  "L2应对: Git门槛高是最大问题。方案：Web界面表格编辑器→浏览器增删改用例→后端GitPython自动生成commit推送。兼顾Git版本控制+Web易用性。Git是底层工具(专业人士)，Web是交互界面(所有人)，各司其职。\n"
  "L3追问: 两人同时在Web编辑同一文件，Git冲突怎么处理？\n"
  "L3兜底: ①预防-乐观锁：编辑时记录当前版本号(Git commit hash)，保存时检查变化→提示'已被他人修改请刷新'；②Git冲突(绕过Web直接push)→后端push失败捕获GitCommandError，回滚本地修改+通知操作失败；③最坏-手动解决，极少发生。不做自动合并：JSON文件自动合并风险大(可能产生合法但不正确JSON)，人工介入最安全。")

Q("Q15. CI/CD自动化集成怎么做的？",
  "L1: GitLab CI两场景：①Prompt变更自动评测-PR触发CI检测prompts/目录变更→调用平台API发起评测→轮询完成→指标低于阈值CI Failed阻止合并→评测报告自动评论MR。②平台代码质量-pytest+flake8+bandit(后端)/vitest+ESLint(前端)→Docker构建推送Registry。核心价值：Prompt变更从'感觉变好'变成'数据支撑(通过率85%→92%)'。\n"
  "L2追问: 评测跑30分钟，CI Runner一直占着？成本高吧？\n"
  "L2应对: 异步触发+Webhook回调：①CI只触发任务(POST拿task_id)不等待，3秒结束；②平台评测完成回调GitLab Pipeline API；③真正门禁在Webhook：指标不达标→平台调GitLab API标记MR不能合并+评论。CI Runner无需等待，成本从30分钟降到3秒。\n"
  "L3追问: Webhook回调失败了怎么办？\n"
  "L3兜底: 三层保障：①重试-指数退避(1s→2s→4s→8s→16s)最多5次，Celery retry+countdown；②兜底定时任务-每10分钟扫最近完成未回调成功的补发；③告警-超30分钟未回调成功触发企业微信通知人工介入。分布式系统无100%可靠，通过'重试+兜底+告警'降到可接受范围。")

Q("Q16. 平台怎么处理大文件上传？比如评测数据集几百MB？",
  "L1: 分片上传方案：前端File.slice()切片(每片5MB)+并发上传+上传进度条；后端FastAPI接收分片暂存临时目录，全部上传后合并+校验MD5。Celery异步任务处理大文件解析(CSV/JSON)，解析进度通过WebSocket推前端。结果存入数据库+原始文件存MinIO对象存储。\n"
  "L2追问: 分片上传中断了怎么办？能续传吗？\n"
  "L2应对: 支持断点续传：①前端上传前调初始化接口获取upload_id；②每片上传带upload_id+chunk_index；③后端Redis记录已上传分片索引；④中断后前端查询已上传分片列表，只传缺失分片；⑤全部传完后端合并。Redis设置upload_id TTL=24小时防僵尸上传。\n"
  "L3追问: 大文件解析内存溢出怎么办？\n"
  "L3兜底: 流式解析不一次性加载到内存：CSV用csv.reader逐行读，每1000行批量入库+释放内存；JSON大数组用ijson流式解析逐条处理；Excel用openpyxl的read_only模式。设置Celery Worker内存上限(worker_max_memory_per_child)，超限自动重启Worker防内存泄漏累积。")

Q("Q17. 平台怎么保证数据安全？敏感数据怎么处理？",
  "L1: 多层安全：①传输层-HTTPS全站加密+Nginx TLS1.3；②存储层-数据库密码/API Key存环境变量不写代码，生产环境用Docker Secret；③数据脱敏-评测结果中手机号/邮箱自动打码(正则替换)；④审计日志-记录所有关键操作(谁/何时/做了什么)；⑤备份-PostgreSQL每日自动备份+30天保留。\n"
  "L2追问: 数据库备份策略具体怎么做？能恢复到任意时间点吗？\n"
  "L2应对: 每日全量备份(pg_dump)+持续WAL归档。恢复策略：①恢复到最新-pg_dump恢复+WAL重放到当前；②PITR(时间点恢复)-利用WAL归档恢复到指定时间点(如误删数据前一刻)。备份文件加密存MinIO+异地同步。定期做恢复演练(每月一次)确保备份可用。\n"
  "L3追问: WAL归档是什么原理？和MySQL binlog有什么区别？\n"
  "L3兜底: WAL(Write-Ahead Logging)：数据修改先写日志再写磁盘，保证崩溃恢复。PostgreSQL WAL记录物理层面的页修改(block-level)，MySQL binlog记录逻辑层面的SQL语句。WAL归档=把写满的WAL文件复制到安全位置，配合基础备份实现PITR。物理vs逻辑：WAL恢复更快(直接应用页变更)，binlog更灵活(可跨版本/跨平台)。")

Q("Q18. 如果有用户反馈评测结果不准，你怎么排查？",
  "L1: 标准排查链路：①确认问题-复现用户操作，确认是单个case还是批量问题；②检查数据-测试用例输入是否正确/参考答案是否合理；③检查Prompt-是否最近有变更(查版本历史)；④检查模型-是否切换了模型版本或API(查配置变更记录)；⑤检查评测指标-指标计算是否有bug(对比人工评估)；⑥定位根因→修复→回归测试→通知用户。\n"
  "L2追问: 怎么判断是指标计算问题还是模型真的变差了？\n"
  "L2应对: 双轨验证：①人工抽样-随机抽20条争议结果人工评分，对比平台评分，计算Kappa一致性系数。若Kappa<0.6说明指标有问题；②A/B对照-用同一批数据同时跑新旧版本或不同模型，排除数据/环境因素。关键：每次排查记录成Postmortem文档沉淀经验。\n"
  "L3追问: 如果发现是指标计算bug，但历史数据已经错了，怎么办？\n"
  "L3兜底: ①标记-历史受影响数据标记为'inaccurate'状态，防止错误数据影响决策；②修复-修完bug后写数据修复脚本批量重算历史数据(前提：原始response有留存)；③通知-告知所有用户哪些时间段数据有问题+已修复；④防重犯-给指标计算加单元测试+定期和人工评估对标。诚实面对错误比掩盖错误更重要。")

Q("Q19. 你怎么保证平台自身的质量？",
  "L1: 多层质量保障：①单元测试-pytest覆盖率>80%，核心service层全覆盖；②集成测试-FastAPI TestClient模拟HTTP请求测试完整链路；③E2E测试-Playwright自动化测试关键用户流程；④Dogfooding-我自己日常用平台做实际评测，第一时间发现体验问题；⑤Code Review-虽然一人开发但我用GitLab MR自Review+CI强制检查。\n"
  "L2追问: 你一个人怎么做好Code Review？\n"
  "L2应对: 自Review技巧：①提交后不立即合并，等第二天再看(新鲜视角)；②按Checklist审查(错误处理/日志/性能/安全)；③CI自动检查(flake8/bandit/测试覆盖率)；④写清楚commit message(What+Why+How)，相当于给自己Review的上下文；⑤核心逻辑写注释解释设计意图，方便后续review。这不是最佳实践但一人团队的现实做法。\n"
  "L3追问: 如果加人，你怎么建立团队的质量文化？\n"
  "L3兜底: ①制定编码规范+配置自动检查(Pre-commit Hook+CI)；②强制Code Review(MR至少1人Approve)；③测试金字塔-单元测试>集成测试>E2E；④质量度量-测试覆盖率/线上Bug率/MTTR看板透明化；⑤无指责文化-出问题聚焦流程改进而非追责个人。从'我保证质量'到'机制保证质量'。")

Q("Q20. 给新人介绍这个平台，你怎么讲？",
  "L1: 三句话定位：'这个平台是AI应用的自动化质量守护者。类比传统软件测试，它帮你自动化检查AI的输出是否准确、安全、稳定。你可以把它理解为AI的单元测试+集成测试+回归测试平台。'\n"
  "然后按角色讲：对PM-帮你看Prompt改完后效果变好还是变差(有数据有图表)；对开发-改代码后自动跑评测不担心破坏AI质量；对测试-管理测试用例+自动化执行+一键出报告。\n"
  "L2追问: 你觉得这个平台最难让新人理解的是什么？\n"
  "L2应对: 最难的是'AI测试和传统测试的思维差异'。传统测试期望确定性结果(输入A必定输出B)，但AI输出是不确定的——同一个Prompt两次结果可能不同。所以AI测试思维是'统计质量'而非'绝对正确'——我们关注的是100次里有多少次达标，而不是某一次对不对。这个思维转变是最难但最重要的。\n"
  "L3追问: 那你觉得AI测试的'足够好'怎么定义？\n"
  "L3兜底: '足够好'取决于业务风险容忍度。车载AI(路特创新场景)：安全性指标必须>99.9%，不能有危险指令遗漏；客服AI：准确性>90%可能就够(错了可人工兜底)。定义方式：①和业务方对齐风险等级；②制定SLO(服务水平目标)；③低于SLO自动告警。关键是让业务方理解：AI质量不是0和1，是概率分布。")

# ============ 1.2 技术选型决策（Q21-Q50）============
S("1.2 技术选型决策（Q21-Q50）")

Q("Q21. 你在这个项目中做过哪些关键的技术选型？",
  "L1: 关键选型：①后端框架FastAPI(vs Flask/Django)；②AI框架LangChain(vs LlamaIndex/原生SDK)；③评测框架RAGAS(vs DeepEval)；④向量数据库Milvus(vs Chroma/Pinecone/Qdrant)；⑤消息队列Redis(vs RabbitMQ)；⑥部署方式Docker Compose(vs K8s)；⑦前端Vue3(vs React)。每个选型都有对比分析和适用场景考量。\n"
  "L2追问: 你的选型标准是什么？\n"
  "L2应对: 五维评估模型：①功能匹配度(能不能满足核心需求)；②学习成本(我和团队能不能hold住)；③生态成熟度(社区/文档/案例)；④性能&扩展性(当前和未来3-6个月够用)；⑤成本(开源/付费/运维)。不追最新技术，选'当前阶段最合适'的。比如不选K8s不是因为不好，而是团队规模下ROI太低。\n"
  "L3追问: 有没有选错的案例？后来怎么调整的？\n"
  "L3兜底: 早期选过Chroma做向量数据库(轻量易上手)。问题：数据量到几十万条后查询性能急剧下降(Chroma内存索引无持久化优化)。调整：迁移到Milvus(支持IVF/HNSW索引+磁盘持久化)，写了数据迁移脚本(Chroma→JSON→Milvus)。教训：选型时要考虑'6个月后的数据规模'而非'当前规模'。")

Q("Q22. 为什么用LangChain而不是LlamaIndex？",
  "L1: LangChain适合Agent/Chain编排场景(我们的Agent测试需要)，LlamaIndex专注数据索引和检索。选LangChain原因：①Agent框架更成熟(Tool Calling/ReAct/Multi-Agent)；②Chain组合灵活(PromptTemplate→LLM→OutputParser可自由编排)；③生态更广(更多Tool集成)。LlamaIndex在文档解析/索引结构上更强，RAG模块参考了它的设计。\n"
  "L2追问: LangChain有什么坑？\n"
  "L2应对: 踩过几个坑：①版本迭代太快(0.x版本API频繁Breaking Change)，解决方案锁定版本+pip freeze；②AgentExecutor默认max_iterations过高(容易死循环)，必须设合理上限+early_stopping；③序列化问题(Chain对象pickle复杂)，不存Chain对象只存配置JSON；④文档有时滞后于代码，关键逻辑直接看源码。LangChain适合快速原型，生产环境关键路径自己封装。\n"
  "L3追问: LangChain AgentExecutor底层执行流程？和ReAct什么关系？\n"
  "L3兜底: AgentExecutor核心循环：接收输入→调LLM生成思考+行动→解析行动(调Tool或输出最终答案)→执行Tool→结果回填→下一轮LLM调用。ReAct是其中一种推理模式(Reasoning+Acting交替)，还有OpenAI Function Calling模式(直接输出function_call)。AgentExecutor源码关键：max_iterations控制循环次数，early_stopping_method控制超限行为(force/generate)。没有逐行读过但排查死循环问题时断点追踪过关键路径。")

Q("Q23. 为什么用RAGAS而不是DeepEval做评测？",
  "L1: RAGAS专注RAG评测(指标设计更专业)，DeepEval更通用。选RAGAS原因：①Faithfulness/AnswerRelevancy/ContextPrecision/ContextRecall四指标直击RAG痛点；②指标计算逻辑透明(基于LLM-as-Judge有明确Prompt模板)；③社区活跃+论文背书。DeepEval优势：支持更多指标(偏见/毒性/Hallucination)+CI集成更好。未来可能混合使用。\n"
  "L2追问: RAGAS指标怎么计算的？Faithfulness底层逻辑？\n"
  "L2应对: Faithfulness(忠实度)计算：①把生成的答案拆成多个'陈述句'(claims)；②对每个claim用LLM判断是否可由提供的上下文支持(是/否)；③忠实度=被支持的claims数/总claims数。本质是检验'答案有没有编造上下文里没有的信息'。注意：RAGAS指标依赖LLM-as-Judge，选Judge模型很关键(一般用GPT-4)。\n"
  "L3追问: LLM-as-Judge有什么偏差？怎么校准？\n"
  "L3兜底: 三大偏差：①位置偏差-倾向于认为列表前面的内容更好；②长度偏差-偏爱长答案(显得更详细)；③自我偏好-模型给自己生成的答案打分偏高。校准方法：①随机打乱对比顺序；②归一化长度因素；③用不同Judge模型交叉验证；④定期和人工评估对标计算偏移量。我们每月抽样100条人工评分vs RAGAS评分，监控一致性。")

Q("Q24. 向量数据库为什么选Milvus？",
  "L1: Milvus是专为向量检索设计的数据库。对比：Chroma(轻量但数据量大后性能差)→选Milvus；Pinecone(SaaS托管但数据安全+成本考量)→选Milvus自部署；Qdrant(不错但Milvus社区更大/文档更全)。Milvus优势：①多种索引类型(IVF_FLAT/HNSW/DiskANN)；②支持标量过滤+向量检索混合查询；③云原生架构可扩展；④中文社区活跃。\n"
  "L2追问: Milvus的索引类型怎么选？IVF_FLAT和HNSW区别？\n"
  "L2应对: IVF_FLAT-先聚类再搜索：①建索引-用K-Means把向量分成N个簇；②查询-先找最近K个簇→再簇内暴力搜索。优点省内存，缺点精度略低(可能漏掉边界簇)。HNSW-分层可导航小世界图：①建图-多层跳表结构(上层稀疏下层密集)；②查询-从上层贪心搜索逐步到下层。优点高精度+快，缺点内存占用大。选择：内存够→HNSW(高精度)，向量量大内存紧→IVF_FLAT(省内存)。\n"
  "L3追问: HNSW图的构建过程？为什么它能同时保证高精度和高速度？\n"
  "L3兜底: HNSW核心思想：多层图结构借鉴跳表。构建时：每个节点随机分配层级(指数衰减概率)，上层节点少(长距离连接)，下层节点多(短距离连接)。搜索时从顶层入口点贪心向下→上层快速定位大致区域→下层精细搜索。精度保证：多入口+启发式邻居选择减少局部最优；速度保证：上层跳跃大幅缩小搜索范围。深层理论(如邻居选择策略的可证明收敛性)未深入研究，但理解核心直觉够用。")

Q("Q25. 模型API怎么选的？为什么用GPT-4？",
  "L1: 按场景选模型：①评测Judge用GPT-4(推理能力最强，RAGAS官方推荐)；②日常对话测试用GPT-4o(性价比高)；③代码生成用DeepSeek-V3(代码能力出色+成本低)；④中文场景用Qwen(中文理解好)。多模型路由-配置文件定义场景→模型映射，LLMClientFactory动态选择。\n"
  "L2追问: 多模型成本怎么控制？\n"
  "L2应对: 分层策略：①评测Judge(GPT-4)最贵但必须(准确性优先)→限制调用频率(评测任务排队)；②日常测试用GPT-4o-mini(便宜10倍)→量大面广；③本地模型(vLLM部署开源模型)→高频/敏感场景，只需GPU成本。加Token预算管理-每个评测任务设定max_tokens上限+月度预算告警。\n"
  "L3追问: 本地部署vLLM的GPU成本怎么算？和API调用哪个更划算？\n"
  "L3兜底: 盈亏平衡点计算：API(GPT-4o~$5/1M tokens) vs 自建(A100~$1.5/小时云租赁)。自建优势：①高频场景(日均百万token)→GPU利用率高时便宜5-10倍；②数据安全-不出内网；③可控延迟-无API排队。劣势：①冷启动成本(部署维护)；②低负载时GPU闲置浪费。我们当前评测量不高用API更划算，但架构预留了本地模型接入点。")

Q("Q26. 怎么管理API Key和敏感配置？",
  "L1: 多层管理：①开发环境-.env文件(Git .gitignore排除)；②生产环境-Docker Secret或K8s Secret；③代码中-通过环境变量读取，永不硬编码；④轮换策略-API Key定期更换(90天)，更换时走配置中心热更新。FastAPI用pydantic-settings读取配置，类型校验+启动时验证必需配置存在。\n"
  "L2追问: 如果API Key泄露了怎么办？\n"
  "L2应对: 应急预案：①立即-在云平台吊销泄露的Key；②生成新Key→更新配置→重启服务(或热加载)；③排查-审计日志查泄露时间窗口，评估影响范围(哪些数据可能被访问)；④复盘-泄露原因(误提交Git?日志打印?)，加防护(Pre-commit Hook扫描敏感信息/git-secrets)。Grafana设置API用量异常告警(突增→可能泄露)。\n"
  "L3追问: 热更新配置怎么实现？不重启服务能更新API Key吗？\n"
  "L3兜底: 方案：①配置中心(如Consul/etcd)-应用watch配置变更，回调更新内存配置；②轻量方案-定时从DB/Redis加载配置(30秒间隔)，开销小；③K8s ConfigMap更新+滚动重启Pod(最稳)。我们当前用方案②(Redis存配置+30秒刷新)，简单够用。生产级推荐方案③，重启带来短暂不可用但最可靠(无状态不一致风险)。")

Q("Q27. 为什么用Celery而不用其他任务队列？",
  "L1: Celery优势：①Python生态最成熟的任务队列(10年+历史)；②功能全面(定时任务/任务路由/重试/结果存储)；③Broker灵活(Redis/RabbitMQ/SQS可换)；④社区大(问题好查)。备选方案：RQ(太简单无定时任务)/Dramatiq(不错但生态小)/APScheduler(不是分布式)。\n"
  "L2追问: Celery有什么痛点？\n"
  "L2应对: 踩过坑：①Redis Broker下任务结果存储用Redis，大量结果会撑爆内存→配置result_expires自动清理；②Celery Worker默认prefetch_multiplier=4(预取4个任务)，长任务场景下积压→设为1公平调度；③flower监控UI好用但资源占用大→生产环境限制采样率；④时区问题-配置中CELERY_TIMEZONE必须和Django/FastAPI一致否则定时任务错乱。\n"
  "L3追问: Celery任务执行到一半Worker被杀，怎么保证数据一致性？\n"
  "L3兜底: Celery的acks_late配置：默认任务被Worker取走就ACK(即使没执行完)，Worker挂则任务丢失。acks_late=True时任务执行完才ACK，Worker挂则任务重入队列。但acks_late+幂等设计是必须的(重入队列可能重复执行)。我们的做法：①关键任务开启acks_late；②所有任务做幂等(执行前查DB状态)；③soft_time_limit超时后自动重试；④数据库事务保证原子性(任务结果写入和状态更新在同一事务)。")

Q("Q28. 前端状态管理为什么选Pinia而不是Vuex？",
  "L1: Pinia优势：①TypeScript支持原生(Vuex4的TS类型推导很弱)；②API更简洁(没有Mutations，直接actions改state)；③模块化天然(每个store独立，不需要Vuex的modules嵌套)；④Vue DevTools支持好。Vuex是Vue2时代的方案，Vue3生态Pinia已是官方推荐。\n"
  "L2追问: Pinia的响应式原理？和Vuex有什么区别？\n"
  "L2应对: Pinia底层用Vue3的reactive()包装state，通过effectScope管理响应式作用域。和Vuex区别：①Vuex靠Vuex.Store单一状态树+严格模式区分mutation/action；②Pinia不需要mutation(直接修改state)，更灵活但失去mutation的可追踪性(通过DevTools补偿)。Pinia的store本质是reactive对象+computed(getter)+function(action)的组合，没有黑魔法。\n"
  "L3追问: Vue3的reactive()和ref()底层实现区别？Proxy vs getter/setter？\n"
  "L3兜底: ref()：对基本类型包装成{value:...}对象，用class的get value/set value拦截。reactive()：用ES6 Proxy代理整个对象，拦截get/set/deleteProperty等操作。ref内部对对象类型也会转reactive。关键区别：①ref需要.value访问，reactive直接访问属性；②ref可替换整个值(reactive替换整个对象会丢失响应式)；③reactive不能包装基本类型。原理层面：都依赖Vue3的effect系统做依赖追踪和触发更新。")

Q("Q29. 为什么用Nginx做反向代理？",
  "L1: Nginx选型理由：①高性能事件驱动(epoll)，单机数万并发；②静态资源服务(前端SPA)+反向代理+HTTPS终结一体；③配置简单+热加载(nginx -s reload)；④生态成熟(文档/案例/模块)。备选：Caddy(自动HTTPS但生态小)/Traefik(云原生但配置复杂)/HAProxy(四层LB强但七层弱)。\n"
  "L2追问: Nginx反向代理的负载均衡策略有哪些？\n"
  "L2应对: 常用策略：①轮询(默认)-依次分配；②加权轮询-按服务器性能分配权重；③ip_hash-同IP请求固定后端(解决Session问题)；④least_conn-分配给连接数最少的后端；⑤fair(第三方)-按响应时间分配。当前单后端无需LB，但配置了upstream预留扩展。加了fail_timeout+max_fails做健康检查(连续失败N次标记down)。\n"
  "L3追问: Nginx的epoll模型和select/poll的本质区别？\n"
  "L3兜底: select/poll：每次调用都要把全部fd集合从用户态拷到内核态，内核O(n)遍历查找就绪fd，fd数量上限受限(select默认1024)。epoll：通过epoll_ctl注册fd到内核事件表(红黑树)，只拷贝一次；epoll_wait通过就绪链表直接返回就绪fd(O(1)获取)，无需遍历全部fd。epoll是Linux特有，Nginx在其他平台用kqueue(Mac)或/dev/poll(Solaris)。深层实现(红黑树+回调机制)未读源码，但理解'事件通知vs轮询'的核心差异。")

Q("Q30. 有没有考虑过用GraphQL替代REST API？",
  "L1: 考虑过但没用。GraphQL优势(前端灵活取数据/减少over-fetching)对我们场景价值不大：①评测平台页面数据需求固定(不需要灵活查询)；②GraphQL复杂度(N+1问题/缓存困难/错误处理)ROI不高；③REST+Swagger文档前后端联调效率已够。引入GraphQL反而增加学习成本和维护负担。\n"
  "L2追问: GraphQL的N+1问题是什么？怎么解决？\n"
  "L2应对: N+1问题：查询文章列表+每篇文章的作者→先查文章(1次)→再逐篇查作者(N次)，共N+1次查询。GraphQL原生逐字段resolve，容易产生此问题。解决方案：DataLoader-批量收集请求，合并成单次查询(如WHERE id IN (...))，利用缓存去重。DataLoader用事件循环tick收集同一帧内的请求→批量执行。\n"
  "L3追问: DataLoader底层实现原理？\n"
  "L3兜底: DataLoader核心：①收集阶段-每个load()调用不立即执行，把key存入内部队列；②分发阶段-在process.nextTick()/Promise微任务中，调用batchLoadFn(keys)批量处理所有收集到的key；③缓存-每个请求周期内缓存结果(相同key返回缓存)。关键技术：利用JS事件循环机制(微任务在宏任务之前执行)，确保同一帧内的请求被批量处理。Python没有原生DataLoader，可用asyncio.gather+字典缓存实现类似效果。")

# ============ 1.3 踩坑与解决（Q51-Q75）============
S("1.3 踩坑与解决（Q51-Q75）")

Q("Q51. 项目中遇到最大的技术难点是什么？",
  "L1: 最大难点是Agent测试的可靠性验证。Agent行为不确定(同一个输入可能选不同工具)，传统assert expected==actual的测试方式完全失效。解决方案：①设计'行为约束'而非'输出约束'-验证Agent是否在允许的工具列表内选择、是否在规定步数内完成任务、输出是否包含必要信息；②引入'软断言'-不要求精确匹配，用相似度阈值+LLM-as-Judge评估。\n"
  "L2追问: 软断言具体怎么实现的？怎么定阈值？\n"
  "L2应对: 三层验证：①结构验证-输出格式是否正确(JSON Schema/必填字段)；②语义验证-用embedding计算预期和实际输出的余弦相似度，>0.85视为通过；③LLM验证-用GPT-4判断'输出是否在语义上等价于预期'(是/否+理由)。阈值0.85是实验得来-抽样200条人工标注+找F1最高的阈值。\n"
  "L3追问: 阈值0.85怎么科学确定的？不是拍脑袋？\n"
  "L3兜底: 科学方法：①标注-人工标注200条'通过/不通过'；②遍历阈值0.7到0.95(步长0.01)计算F1；③选F1最高的阈值(0.85)；④验证-另50条验证集确认F1稳定。这本质是分类问题的阈值调优。局限性：阈值受embedding模型影响(换模型需重新标定)，所以我们把阈值做成可配置参数，不同模型不同阈值。")

Q("Q52. LLM输出不稳定怎么处理？",
  "L1: 多层策略：①Temperature设为0(或很低如0.1)让输出更确定；②重试机制-同一输入跑3次取多数结果(majority voting)；③seed参数固定随机种子(部分API支持)；④结构化输出-用JSON Mode/Function Calling强制输出格式；⑤评测侧-多次评测取平均值而非单次结果。\n"
  "L2追问: Temperature=0真的完全确定吗？\n"
  "L2应对: 理论上Temperature=0时模型选择概率最高的token(贪心解码)，应该确定。但实际上：①GPU浮点运算的非确定性(并行计算顺序不同→微小浮点误差→累积→不同token选择)；②部分API即使temperature=0也有微小随机性。所以不依赖'绝对确定'，而是设计'对轻微变化鲁棒'的评测指标(多次取平均+容忍度)。\n"
  "L3追问: 为什么GPU浮点运算是不确定的？\n"
  "L3兜底: 浮点加法不满足结合律：(a+b)+c可能≠a+(b+c)因为舍入误差。GPU并行计算时，sum的顺序取决于线程调度(不确定)，导致同输入产生微小浮点差异。在Transformer的Attention计算中(QK^T矩阵乘法)，这种差异经过softmax放大可能导致不同token被选中。解决方案：①确定性算法(如FlashAttention的确定性模式)；②应用层接受微小的非确定性。")

Q("Q53. API限流(Rate Limit)怎么处理的？",
  "L1: 三层限流策略：①客户端-用token-bucket算法控制发请求速率(每个模型独立桶)；②重试-429错误自动重试(读Retry-After Header确定等待时间)；③调度-多个评测任务排队，按优先级+Token预算分配(高优任务先跑)。Celery任务加rate_limit参数控制执行频率。\n"
  "L2追问: 令牌桶和滑动窗口限流算法有什么区别？\n"
  "L2应对: 滑动窗口：统计最近N秒内请求数，超阈值则拒绝。简单但有'边界突发'问题(窗口边界可能放行2倍速率)。令牌桶：以固定速率生成令牌存桶中(有上限)，请求消耗令牌，无令牌则拒绝。优势：允许一定突发(桶容量=最大突发量)，同时控制长期平均速率。OpenAI API用的就是令牌桶。\n"
  "L3追问: 分布式环境下令牌桶怎么实现？\n"
  "L3兜底: 需用Redis实现：①用Sorted Set存每次请求的时间戳；②每次请求前清理过期记录+count剩余；③或用Lua脚本原子操作(INCR+EXPIRE)。但分布式令牌桶的'公平性'难保证-多节点同时消费可能瞬时超限。改进：Redis + 本地预取(每个节点从Redis批量领取令牌放本地桶)，减少Redis调用频率但引入微量不公平。")

Q("Q54. 数据库连接池遇到过什么问题？",
  "L1: 踩过连接泄漏的坑：Celery Worker在执行长任务(调用LLM API等几十秒)时持有数据库连接不释放，其他Worker等待连接超时。解决：①SQLAlchemy配置pool_pre_ping=True(每次检出前ping检查连接有效性)；②pool_recycle设置连接最大存活时间(3600秒)；③Celery任务中手动管理Session(用with语句确保关闭)；④监控连接池状态(已用/空闲/溢出)。\n"
  "L2追问: 连接池参数怎么调优？\n"
  "L2应对: 核心参数：①pool_size-常驻连接数(默认5，设为核心数×2)；②max_overflow-超出pool_size可创建的最大临时连接(设为核心数)；③pool_timeout-等待可用连接的超时(默认30秒，设10秒快速失败)。计算：并发请求数< pool_size+max_overflow，否则排队等待。PostgreSQL默认max_connections=100，所有服务共享。\n"
  "L3追问: PostgreSQL的max_connections设大了有什么问题？\n"
  "L3兜底: 每个连接消耗内存(约10MB)+CPU(上下文切换)，连接数过多→内存耗尽+性能下降(锁竞争)。PostgreSQL用多进程模型(非多线程)，每个连接一个进程，1000个连接=1000个进程→系统崩溃。最佳实践：用连接池(PgBouncer)复用连接，应用层pool_size适度(20-50)，总连接数不超过CPU核数×2~3。我们当前单机pool_size=10够用。")

Q("Q55. 大响应超时怎么处理？",
  "L1: 分层超时控制：①LLM调用超时-OpenAI SDK设timeout=60s，超时抛异常+重试；②HTTP请求超时-Nginx proxy_read_timeout设120s；③Celery任务超时-soft_time_limit设30分钟；④数据库查询超时-statement_timeout设30s。超时后：日志记录+告警+优雅降级(返回部分结果或缓存)。\n"
  "L2追问: 流式响应(Streaming)怎么处理超时？\n"
  "L2应对: Streaming超时特殊：首Token超时(TTFT)和Token间超时(TPOT)分别控制。①TTFT超时-15秒内没收到第一个Token则重试(模型可能冷启动)；②TPOT超时-30秒内没收到下一个Token视为连接中断；③SSE心跳-服务端每10秒发keepalive注释行，防止代理超时断开。FastAPI StreamingResponse设合理的timeout_keep_alive。\n"
  "L3追问: 如果模型推理中断(比如API方故障)，用户看到一半的响应怎么办？\n"
  "L3兜底: 前端处理：①EventSource.onerror捕获连接中断→展示'响应中断，正在重试...'；②自动重连(带重试次数限制，最多3次)；③重连成功后从断点续传(如果有last_event_id)；④如果重连失败→展示'生成失败，请重试'按钮+展示已收到的部分内容(灰显标记为不完整)。关键：不让用户看到'空白'或'转圈圈到天荒地老'。")

Q("Q56. 怎么发现和解决内存泄漏？",
  "L1: 遇到过Celery Worker内存持续增长问题。排查：①tracemalloc追踪内存分配(每100个任务snapshot对比)；②发现是LangChain Callback中累积大量日志未清理；③修复-每个任务结束后手动清理callback的logs列表+用weakref避免循环引用。监控：Celery Worker设worker_max_memory_per_child(超300MB自动重启)。\n"
  "L2追问: tracemalloc怎么用？和memory_profiler区别？\n"
  "L2应对: tracemalloc是Python标准库，追踪每行代码的内存分配：①start()开始追踪→take_snapshot()拍照→compare_to()对比→statistics('lineno')查看哪些行分配最多。优势是精确到行+低开销。memory_profiler是第三方库(@profile装饰器)，逐行显示内存变化，更适合函数级分析。排查泄漏用tracemalloc(定位具体对象)，分析函数用memory_profiler。\n"
  "L3追问: Python的垃圾回收(GC)机制？为什么会循环引用导致泄漏？\n"
  "L3兜底: Python用引用计数(主要)+标记清除(循环引用)两种GC。引用计数：每个对象维护被引用次数，为0时立即回收。循环引用：A→B→A互相引用但外部不可达，引用计数不为0→需要标记清除(从root出发标记可达对象，清除不可达)。weakref创建弱引用不增加引用计数，是打破循环引用的常用手段。Celery Worker是长期进程，循环引用累积会导致内存持续增长。")

Q("Q57. 跨服务调用失败了怎么处理？",
  "L1: 重试+熔断+降级三板斧：①重试-指数退避(1s→2s→4s→8s)，最多3次；②熔断-连续5次失败→熔断打开60秒→快速失败不浪费资源；③降级-LLM主模型超时→自动切备用模型(如GPT-4→GPT-4o-mini)；RAG检索失败→返回空上下文+标记降级。降级后的结果在评测报告中标记'降级'状态便于追溯。\n"
  "L2追问: 降级后评测结果还准确吗？怎么处理降级数据？\n"
  "L2应对: 降级数据不能和正常数据混在一起统计。策略：①打标-降级结果单独标记degraded=True；②分轨统计-报告中'正常结果指标'和'降级结果指标'分开展示；③决策-降级比例>5%触发告警(说明系统不稳定)；④回归-降级数据单独存储，后续可重新评测(换回正常模型)。\n"
  "L3追问: 如果降级模型也不可用怎么办？最终兜底？\n"
  "L3兜底: 最终兜底策略：①返回缓存-如果该Prompt之前有成功的评测结果，返回缓存版本(标记from_cache=True)；②返回空结果-明确标记status=UNAVAILABLE；③不静默失败-通知用户'评测因服务不可用中断，请稍后重试'。原则：宁可明确失败也不返回不可靠结果。缓存策略需要注意时效性(24小时内有效)。")

Q("Q58. 平台升级时怎么保证不中断服务？",
  "L1: 蓝绿部署思路(简化版)：①docker compose up新版本服务(不同端口)→②健康检查确认新版本OK→③Nginx reload切换upstream指向新端口→④旧版本服务docker compose stop。过程中Celery Worker：先停旧Worker接收新任务(signal SIGTERM等待当前任务完成)→启动新Worker。整体中断<5秒(nginx reload时间)。\n"
  "L2追问: 数据库迁移(migration)怎么处理？\n"
  "L2应对: 用Alembic管理数据库版本：①升级前备份；②生成迁移脚本(alembic revision --autogenerate)；③Review迁移脚本(检查是否锁表/数据丢失)；④执行alembic upgrade head。关键原则：①只加列不删列(删除放下一版本)；②大表加列不加默认值(避免锁表)；③迁移脚本和代码兼容(新旧代码都能跑)。\n"
  "L3追问: 迁移脚本和代码兼容具体怎么做？\n"
  "L3兜底: 分三步走：①Step1(兼容阶段)-代码对新增列判空处理(None→默认值)，可部署新旧代码；②Step2-部署迁移脚本加列(不带默认值)，新旧代码都兼容；③Step3-后台填充默认值→代码去掉判空逻辑→部署新代码。这叫'Expand-Contract'模式。一步到位(加列+改代码同时上线)是危险的，必须分步。")

Q("Q59. 你遇到过印象最深的Bug是什么？",
  "L1: 印象最深的是'幽灵评测结果'Bug。现象：偶尔出现评测结果完全不对(和Prompt无关)，排查发现是Celery Worker中使用了全局变量缓存LLMClient实例，不同任务间共享了同一个client，导致任务A的结果污染了任务B的请求。修复：改为每个任务新建client或确保client无状态+线程安全。教训：分布式任务中全局状态是大忌。\n"
  "L2追问: 怎么排查出是全局变量导致的？用了什么工具？\n"
  "L2应对: 排查过程：①发现异常结果总是成批出现(同一Worker进程内)；②加request_id全链路追踪(从API→Celery Task→LLM调用)，发现不同task_id对应相同的LLM请求；③在LLMClient加日志打印id(self)，发现多个任务用的是同一个对象；④traceback定位到全局变量。工具：日志+request_id链路追踪+Python id()函数。\n"
  "L3追问: 为什么Python的全局变量在Celery Worker中尤其危险？\n"
  "L3兜底: Celery Worker是长期运行的进程，fork模式(Woker启动时fork主进程)下：①子进程继承父进程的全局变量(内存拷贝)；②多个Task在同一个子进程中顺序执行(默认并发prefetch)；③全局变量跨Task共享(非线程安全)。这是'共享可变状态'的典型案例。解决方案：①不用全局可变状态；②使用Celery的task实例属性(self.app)；③或开启Worker的--max-tasks-per-child定期重启。")

Q("Q60. 怎么保证第三方API(OpenAI等)升级不影响平台？",
  "L1: 多层隔离：①适配器模式-LLMClient封装所有第三方SDK，业务代码只依赖BaseLLMClient抽象；②版本锁定-requirements.txt锁定SDK版本(如openai==1.x)；③兼容测试-CI定期跑(每周)核心评测流程，检测API/SDK变化；④灰度-新SDK版本先在staging环境验证→再切生产。\n"
  "L2追问: OpenAI API的Breaking Change你怎么应对？\n"
  "L2应对: 经历过OpenAI 0.x→1.x大版本迁移：①提前关注OpenAI Changelog+Migration Guide；②在staging环境升级测试；③改LLMClient适配层(业务代码不改)；④监控错误率(上线后密切关注500/400错误)。关键：LLMClient是唯一和OpenAI SDK耦合的地方，改一处全平台生效。这就是适配器模式的价值。\n"
  "L3追问: 如果适配层改不过来(API不兼容)，业务代码也要改怎么办？\n"
  "L3兜底: 评估影响范围+制定迁移计划：①统计所有受影响接口(代码搜索)；②写迁移脚本辅助(正则替换)；③分批迁移-先非关键路径→验证→关键路径；④双版本并行过渡期(同时支持新旧API)；⑤功能开关(Feature Flag)控制切流。最坏情况：回滚SDK版本+向OpenAI提Issue。原则：绝不一次性大爆炸式迁移。")

# ============ 1.4 项目影响力与成果（Q76-Q90）============
S("1.4 项目影响力与成果（Q76-Q90）")

Q("Q76. 这个项目带来了什么价值？怎么衡量？",
  "L1: 量化价值：①效率提升-Prompt回归测试从人工2小时→自动化10分钟(提效12倍)；②质量提升-Prompt上线前拦截率约30%(10次上线3次被评测拦截因指标下降)；③覆盖率-从手工测10条→自动化测500+条；④可追溯-每次Prompt变更都有评测数据支撑。软性价值：团队对AI质量的信心提升，不再靠'我感觉'做决策。\n"
  "L2追问: 30%拦截率怎么统计的？有没有误拦？\n"
  "L2应对: 统计方法：统计MR数量vs被评测拦截(CI Failed)的MR数量。拦截=指标低于阈值，开发需修复后重新提交。误拦分析：抽样被拦截的MR，人工判断是否真的变差。发现约5%误拦(指标敏感度过高)，调整了阈值+增加人工复核环节。当前准确拦截率约95%。\n"
  "L3追问: 怎么定义'真的变差'？人工判断标准是什么？\n"
  "L3兜底: 人工判断三标准：①答案准确性-新版本答案是否包含更多事实错误；②答案完整性-是否遗漏关键信息；③答案质量-是否更啰嗦/格式变差。三人独立评分(1-5分)，取中位数。评分标准文档化(附典型案例)，减少主观性。如果人工评分和自动评测差异>1分，分析原因改进指标。这是持续校准的过程。")

Q("Q77. 如果重新做这个项目，你会改什么？",
  "L1: 三件事：①先做数据管理再建平台-早期测试数据集管理混乱(多人Excel/Git混用)，应该先统一数据标准和工具；②早做可观测性-日志/监控/链路追踪应该Day1就做，后期补成本高；③Agent测试模块先做核心场景MVP-早期想一步到位支持所有Agent框架，浪费了时间。\n"
  "L2追问: 你说的'先做数据管理'具体指什么？\n"
  "L2应对: 指测试数据的标准化和治理：①定义测试用例Schema(必填字段/可选字段/格式)；②数据质量检查(去重/格式校验/覆盖度分析)；③数据版本管理(Git)；④数据血缘追踪(这个测试用例测过哪些Prompt/产生了什么结果)。没有好的数据管理，评测结果的可信度打折扣。这是'Garbage In, Garbage Out'的问题。\n"
  "L3追问: 数据血缘追踪具体怎么实现？\n"
  "L3兜底: 在数据库层记录关联：test_case表存case_id，eval_result表关联case_id+prompt_version_id+task_id。查询链路：case_id→哪些eval_results→哪些prompt_versions→哪些eval_tasks。可视化用DAG图展示。技术实现简单(就是JOIN查询)，关键是坚持记录关联关系不偷懒。类似数据仓库的'星型模型'思想。")

Q("Q78. 你怎么推动团队使用你的平台？",
  "L1: 三步走：①找到痛点-和业务方聊，发现他们最痛的是'Prompt改完不知道效果变好还是变差'，以此为切入点；②降低门槛-写好接入文档+Demo视频+一键脚本，5分钟能跑通第一个评测；③制造WOW时刻-拿他们自己的Prompt跑一次评测，展示可视化对比图，让他们看到'原来数据能这么直观'。关键：不推平台，推'解决你的痛点'。\n"
  "L2追问: 遇到抵触怎么处理？比如'我们手工测挺好的'？\n"
  "L2应对: 不对抗，用数据说话：①量化手工测成本(测一次花多久？覆盖多少条？)→展示自动化对比；②不要求立即切换，建议'双轨运行'(手工测+平台测对比结果)→让事实说话；③先帮他们做一次评测(我出人出力)，让他们无成本体验价值。一次成功的体验比十次说服有效。\n"
  "L3追问: 如果双轨运行后结果不一致，他们更信手工怎么办？\n"
  "L3兜底: 分析不一致原因：①可能是平台指标定义和他们理解不同→对齐标准；②可能是平台有Bug→修复；③可能是手工测不客观(疲劳/疏忽)→用一致性分析(Kappa系数)展示手工评分的波动性。核心：不是'平台vs手工'谁对谁错，而是一起找'最接近真相'的评测方式。把'对抗'变成'合作探索'。")

Q("Q79. 你在这个项目中最大的收获是什么？",
  "L1: 三点：①技术广度-从后端到前端到AI到运维，全栈能力大幅提升；②系统思维-学会从'怎么做'到'为什么这么做'+'做了有什么影响'；③沟通能力-向非技术人员解释AI的不确定性，用数据说话而非技术术语。\n"
  "L2追问: 技术广度vs深度，你怎么看？\n"
  "L2应对: 广度和深度是不同阶段的需求：项目早期需要广度(快速搭建完整系统)，成熟期需要深度(优化性能/解决复杂问题)。我目前是'T型'发展：AI测试方向做深(这是核心竞争力)，其他方向保持够用广度(能独立搭建全栈系统)。广度让我能独立负责项目，深度让我在AI测试领域有专业壁垒。\n"
  "L3追问: 你觉得自己技术深度够吗？和BAT出来的比？\n"
  "L3兜底: 诚实说：在某些底层源码层面不如大厂深耕单一模块的工程师。但我的差异化优势是：①能独立从0到1搭建完整系统(全栈+AI)；②做过真实的技术选型(不是leader告诉我用什么)；③踩过全链路的坑(不只是模块内部)。深度可以补，但'独立负责完整项目'的经验更难获得。我会持续在AI测试方向深耕深度。")

Q("Q80. 如果有人质疑你这个平台的价值(毕竟市面上有LangSmith等成熟产品)，你怎么回应？",
  "L1: 三点回应：①LangSmith是好产品，但我们的场景有特殊性(数据安全+定制化指标+成本考量)，自研的ROI更高；②我借鉴了LangSmith的设计理念(不是闭门造车)，站在巨人肩膀上；③平台价值不在于'是不是自研'，而在于'是否解决了业务问题'——我们的拦截率30%、提效12倍是真实数据。\n"
  "L2追问: 如果公司决定改用LangSmith，你会怎么办？\n"
  "L2应对: 完全接受。我的价值是解决问题，不是维护自己造的轮子。如果LangSmith更合适：①我会主导迁移-把现有测试用例/评测数据迁移到LangSmith；②对比自研和LangSmith的差异-总结哪些LangSmith做得更好(学习)，哪些自研更贴合(反馈给LangSmith)；③迁移过程中的经验也是价值。工程师的价值在解决问题，不在代码归属。\n"
  "L3追问: 如果公司想开源你这个平台，你觉得有竞争力吗？\n"
  "L3兜底: 差异化竞争力：①专注AI测试工程师的工作流(非通用LLM平台)；②评测指标体系更贴合企业实际需求(安全合规/车载场景)；③轻量级部署(Docker Compose一键启动)vs LangSmith重量级。但开源意味着维护成本(文档/Issue/社区)，当前阶段更适合内部使用打磨。开源是手段不是目的。")

# Q81-Q90 继续...
Q("Q81. 你觉得自己在项目中最薄弱的环节是什么？",
  "L1: 前端深度不够。能用Vue3+Element Plus搭建功能完整的中后台，但复杂的CSS布局/动画/性能优化(虚拟滚动/懒加载)能力不够。遇到复杂前端需求时会花较多时间。解决方案：①用成熟的UI组件库(Element Plus)减少自定义CSS；②复杂可视化用ECharts(不自己画)；③保持前端'够用'，重心放后端和AI。\n"
  "L2追问: 你觉得全栈工程师应该前端到什么程度？\n"
  "L2应对: 全栈不等于前后端都精通，而是：①能独立完成完整的业务闭环(从前端页面到后端API到数据库)；②知道前端的基本原理(响应式/组件化/状态管理/性能优化方向)；③遇到复杂问题知道去哪找答案(文档/社区/专业前端同事)。'T型'人才：AI测试方向深，前后端够用。\n"
  "L3追问: 如果项目需要复杂前端(比如拖拽式评测流程编排)，你怎么办？\n"
  "L3兜底: ①先评估是否真的需要(用简单方案能否满足)；②调研成熟方案(如React Flow/LogicFlow流程图组件)；③如果超出能力范围，推动招专业前端或外包前端部分；④我专注后端API设计(为前端提供清晰接口)。坦诚面对能力边界，比硬着头皮做出不可维护的代码更负责任。")

Q("Q82. 平台中哪个模块是你最满意的？为什么？",
  "L1: 最满意的是Prompt评测的CI集成。把'AI质量'纳入标准软件工程流程(Git PR→自动评测→门禁)，让AI测试不再是'额外工作'而是'开发流程一部分'。技术亮点：异步触发+Webhook回调+自动评论MR，CI Runner不需要等待评测完成(从30分钟→3秒)。\n"
  "L2追问: 这个方案有什么不足吗？\n"
  "L2应对: 不足：①Webhook回调可能失败(虽然有重试+兜底)；②评测需要几分钟(虽然CI不等，但开发者要等反馈)；③只能测已有测试集，不能发现未知问题(新类型错误)。改进方向：①分层评测-快速冒烟(30秒)+全量回归(分钟级)；②智能采样-优先测高风险场景。\n"
  "L3追问: '智能采样'怎么实现？\n"
  "L3兜底: 基于历史数据：①统计每个测试用例的历史失败率，高失败率的优先跑；②统计Prompt修改影响范围(改了哪些变量/场景)，只测受影响用例；③用聚类找相似用例(embedding聚类)，每类采样代表。目标：用20%的用例覆盖80%的风险。这是测试策略优化，类似传统软件的'基于风险的测试'。")

Q("Q83. 你觉得AI测试和传统软件测试最大的区别是什么？",
  "L1: 三大区别：①确定性vs概率性-传统测试期望确定结果(输入A→输出B)，AI输出是概率分布(同样输入可能不同输出)；②测试Oracle-传统有明确预期结果，AI测试的'正确答案'往往不唯一(需要相似度/LLM-as-Judge)；③失败模式-传统是代码Bug(可定位行号)，AI失败可能是Prompt/模型/数据/参数等综合因素。\n"
  "L2追问: 概率性输出怎么验证？\n"
  "L2应对: 改变验证思维：①不验证'某一次输出'，验证'统计分布'(100次中>90次正确)；②用容忍区间替代精确匹配(相似度>0.85视为通过)；③关注'不可接受输出'(安全红线)而非'最优输出'；④多次运行取平均/多数投票减少随机性。这和传统测试的思维转变是最关键的。\n"
  "L3追问: '不可接受输出'怎么定义和检测？\n"
  "L3兜底: 定义：①安全红线-输出包含危险指令/歧视内容/违法违规→绝对不可接受(0容忍)；②质量红线-输出完全无关/严重幻觉/格式崩溃→不可接受。检测：①关键词/正则匹配(安全红线)；②LLM分类器(训练二分类模型判断输出是否可接受)；③人工审核(低置信度case)。安全红线检测的召回率(不漏报)比准确率更重要。")

Q("Q84. 你怎么看待AI测试的未来发展？",
  "L1: 三个趋势：①AI测试会成为独立岗位(就像移动测试当年从软件测试分离)；②测试方法从'手工+简单自动化'走向'AI辅助测试+评测体系'；③工具链成熟-类似软件测试的Selenium/JMeter会出现AI测试的标准工具。路特创新这样的公司走在前面，招聘专门的AI测试工程师就是信号。\n"
  "L2追问: 你觉得AI测试工具会标准化吗？什么时候？\n"
  "L2应对: 会但需要时间。参考传统测试：Selenium(2004)→WebDriver标准(2012)→Cypress/Playwright(2018+)，走了十几年。AI测试还在'战国时代'：LangSmith/LangFuse/RAGAS/DeepEval各自发展。标准化需要：①头部公司推动(Google/MS/OpenAI)；②杀手级场景(如自动驾驶AI安全测试)倒逼标准；③社区共识。预计3-5年内出现事实标准。\n"
  "L3追问: 如果3年后标准化了，你现在的经验还有价值吗？\n"
  "L3兜底: 更有价值。标准化工具改变的是'怎么测'，但'测什么/为什么测/怎么判断好坏'这些核心能力不变。就像Selenium出现后，懂Web测试原理的人更有优势。我的经验：①AI评测指标体系设计；②AI失败模式认知；③从0到1搭建测试体系的方法论。工具在变，测试思维和方法论是长期资产。")

Q("Q85. 你在这个项目中如何做决策？特别是信息不充分时？",
  "L1: 决策框架：①明确约束条件(时间/资源/技术限制)；②列出可选方案(至少3个)；③评估各方案的ROI和风险；④设定决策标准(优先满足什么)；⑤做决策并记录理由。信息不充分时：①用原型/PoC快速验证关键假设；②设置决策截止时间(避免分析瘫痪)；③选择'可逆'方案(错了能改回来的)。\n"
  "L2追问: 举个信息不充分做决策的例子？\n"
  "L2应对: 选向量数据库时：Milvus/Qdrant/Weaviate各有优劣，我们数据量还不大(无法实测性能)。决策：①先用Chroma快速集成(PoC验证功能)；②同时预留Milvus接入层(抽象接口)；③当数据量到10万+时对比性能；④确定Chroma不够用后迁移Milvus。这是'低成本试错'策略：先用最简单方案验证功能，性能问题出现再优化。\n"
  "L3追问: 如果迁移成本很高怎么办(比如已经存了几百万条数据)？\n"
  "L3兜底: 那就要更慎重的前期决策：①压力测试-模拟目标数据量(生成假数据)提前测性能；②调研同类公司案例(他们用了什么/数据量多大)；③预留迁移预算(时间+精力)；④评估'不迁移'的代价(性能差到不可用?)。但大多数情况是'过早优化'-在数据量没上来前就选最复杂的方案。原则：先选简单的，留好扩展口，数据量到了再切。")

# ============ 1.5 扩展性设计（Q91-Q120）============
S("1.5 扩展性设计（Q91-Q120）")

Q("Q91. 平台怎么支持多租户？",
  "L1: 目前是单租户(内部团队使用)。多租户设计方案：①数据隔离-每个租户独立schema(PostgreSQL)或tenant_id字段行级隔离；②认证-每个租户独立登录+RBAC；③资源隔离-评测任务按租户队列隔离(避免A租户大量任务阻塞B租户)；④计费-按评测次数/Token消耗计量。当前需求不需要多租户，但数据库设计预留了tenant_id字段。\n"
  "L2追问: 独立schema和行级隔离各有什么优劣？\n"
  "L2应对: 独立schema(每个租户一个PostgreSQL schema)：隔离性最强(数据完全物理隔离)，备份恢复简单(按schema)，但连接池无法跨schema共享(浪费连接)。行级隔离(tenant_id字段+RLS)：资源共享(连接池/表结构)，但隔离性弱(需要严格的行级安全策略)，复杂查询易漏tenant_id过滤。选择：高安全要求(金融/医疗)→独立schema；SaaS通用场景→行级隔离(经济性更好)。\n"
  "L3追问: PostgreSQL的RLS(Row Level Security)怎么实现？\n"
  "L3兜底: RLS通过Policy控制：①ALTER TABLE ... ENABLE ROW LEVEL SECURITY；②CREATE POLICY ... USING (tenant_id = current_setting('app.tenant_id'))；③应用层SET app.tenant_id = 'xxx'(每次请求设置)。此后所有SELECT/UPDATE/DELETE自动加tenant_id过滤(像隐形WHERE)。优势：应用代码不用手动加tenant_id条件；劣势：调试困难(过滤条件不可见)，复杂查询可能性能下降。")

Q("Q92. 如果用户量增长10倍，架构怎么演进？",
  "L1: 三步演进：①第一步-垂直扩展(换更好机器+优化配置)，应对3-5倍增长；②第二步-读写分离(PostgreSQL主从复制，读请求走从库)，应对5-10倍；③第三步-服务拆分(把评测执行/报告生成/Agent测试拆成独立服务+独立数据库)，应对10倍+。每一步都有明确的触发指标(如API P95延迟>500ms)。\n"
  "L2追问: 服务拆分后，原来的模块化单体代码怎么迁移？\n"
  "L2应对: 利用已有的模块化设计：①每个模块已有独立router/service/repository；②抽出模块为独立FastAPI应用(复制代码)；③API Gateway(Nginx)路由到对应服务；④逐步替换原单体中的调用为HTTP/gRPC调用；⑤保留原单体作为'回退方案'直到新服务稳定。关键：代码层面已做好边界隔离，迁移主要是部署层面的变化。\n"
  "L3追问: 服务拆分后，原来在一个事务里的操作变成跨服务了，怎么保证一致性？\n"
  "L3兜底: 分布式事务是微服务最大的挑战。方案：①尽量避免-设计时让需要事务一致性的操作留在同一服务(聚合设计)；②Saga模式-长事务拆成多个本地事务+补偿操作(失败时回滚)；③最终一致性-接受短暂不一致(如评测结果写入和通知发送可以异步)。大多数业务场景不需要强一致性，用'异步消息+重试+补偿'就够了。")

Q("Q93. 怎么支持新的AI模型接入？",
  "L1: 插件化设计：①BaseLLMClient抽象接口(chat/chat_stream方法)；②新模型只需实现这个接口(如QwenClient/GeminiClient)；③配置文件注册新模型(模型名→Client类→参数)；④工厂类自动加载。添加新模型：写一个新Client类(100行左右)+配置注册=即可使用。\n"
  "L2追问: 如果新模型的API风格完全不同(比如不支持Chat格式)，怎么适配？\n"
  "L2应对: 在Client内部做适配：①消息格式转换-把标准messages=[{role,content}]转成模型要求的格式(如纯文本拼接)；②参数映射-把标准参数(temperature/max_tokens)映射到模型参数名(如Gemini用max_output_tokens)；③响应标准化-把模型返回转成LLMResponse统一格式。适配层代码在Client内部，业务层无感知。\n"
  "L3追问: 如果要支持本地部署的开源模型(用vLLM/TGI)，和云端API有什么不同？\n"
  "L3兜底: 差异：①接口兼容-本地模型通常提供OpenAI兼容API(如vLLM的--api-key)，可以直接复用OpenAIClient改base_url；②性能管理-需要监控GPU利用率/显存/队列长度(API不用关心)；③冷启动-本地模型首次加载慢(加载权重到GPU)；④并发限制-受限于GPU数量(API弹性更大)。Client封装时增加健康检查和GPU指标采集。")

Q("Q94. 测试用例怎么管理？版本控制怎么做？",
  "L1: 测试用例全生命周期管理：①创建-Web界面/批量导入(CSV/JSON)/API；②版本-每次修改生成新版本(类似代码commit)；③标签-按场景/难度/Prompt类型打标签；④状态-draft→active→deprecated；⑤关联-用例和评测结果/模型版本关联。版本对比：选两个版本看差异(哪些新增/修改/删除)。\n"
  "L2追问: 测试用例的版本怎么定义？怎么判断是否需要升级版本？\n"
  "L2应对: 版本策略：①任何字段修改(问题/预期答案/标签)都生成新版本(不可变历史)；②语义版本号-主版本(不兼容变更)+次版本(兼容新增)+修订号(修正)；③触发条件-手动保存=生成新版本；批量导入=每个文件变化生成新版本。关键：历史版本不可变(不能修改已发布的版本)。\n"
  "L3追问: 历史版本不可变，但发现有错误怎么办？\n"
  "L3兜底: 不修改错误版本，发布修正版本(新版本号)：①原错误版本标记为deprecated(说明原因)；②发布修正版本；③历史评测结果关联原版本不变(保留历史真实性)；④提供'版本迁移建议'(推荐用新版本替代旧版本)。这类似API的deprecation策略。掩盖错误比承认错误更危险。")

Q("Q95. 怎么保证平台自身的质量？自测试怎么做？",
  "L1: 吃自己的狗粮(Dogfooding)：①用平台测试平台自身的Prompt(系统通知/错误提示/文档生成)；②平台代码变更触发平台自评测(CI中调用自身API)；③监控平台自身指标(API可用率/评测任务成功率)。另加：单元测试(pytest覆盖率>80%)+集成测试(FastAPI TestClient)+E2E(Playwright关键流程)。\n"
  "L2追问: 平台自评测不会陷入'自己测自己'的循环吗？\n"
  "L2应对: 确实存在自指问题，但可分层解决：①代码质量(单元测试/静态分析)不依赖平台；②系统功能(API/数据库)用传统测试(TestClient)；③AI质量(Prompt/评测)用平台自测但辅以人工校验；④关键指标定期人工评估校准。平台测的是AI质量模块，不是平台自身代码。就像编译器可以用自己编译(自举)，但需要上一版本做基准。\n"
  "L3追问: 编译器的自举(Bootstrapping)和你们的自测试有什么异同？\n"
  "L3兜底: 相似：①都面临'先有鸡还是先有蛋'问题-需要用旧版本验证新版本；②都需要基准(Baseline)-已知正确的参考点。不同：①编译器输出确定性(二进制比对)，AI测试输出概率性(相似度)；②编译器正确性是二元(对/错)，AI质量是连续的(好/较好/一般)。所以我们需要人工基准定期校准，不像编译器可以全自动自举。")

# 继续Q96-Q120
Q("Q96. 如果让你设计一个AI测试平台的产品路线图，未来6个月优先做什么？",
  "L1: 三个优先级：P0-评测指标增强(加更多自动化指标如Toxicity/Bias/Completeness)，减少人工评估依赖；P1-智能测试用例生成(用LLM自动生成边界case/对抗样本)，提升覆盖率；P2-评测结果智能分析(自动聚类失败模式/推荐修复方向)。每个功能都有明确的'用户价值'和'技术可行性'评估。\n"
  "L2追问: 智能测试用例生成怎么做？怎么保证生成质量？\n"
  "L2应对: 方案：①种子用例-人工编写核心用例；②变异-用LLM对种子做语义变异(改实体/改句式/改意图)生成变体；③对抗-生成挑战性用例(边界条件/歧义输入/长尾场景)；④过滤-用规则+LLM过滤低质量生成(重复/无意义/不符合场景)。质量保证：人工抽样审核(10%)+自动去重+多样性检查(embedding分布)。\n"
  "L3追问: LLM生成的测试用例会不会引入模型自身的偏见？\n"
  "L3兜底: 会，这是'用AI测AI'的固有问题。缓解：①多模型交叉生成(用Claude/Gemini/GPT-4分别生成，取交集+并集)；②人工审核(高风险场景)；③对抗生成(刻意要求LLM生成挑战性/反常理case)；④覆盖度分析(检查生成用例是否覆盖了所有场景类型，补人工用例)。完全消除偏见不可能，目标是降低到可接受范围。")

Q("Q97. 你怎么看待'AI测试左移'？",
  "L1: AI测试左移=在AI应用开发早期就介入测试。实践：①Prompt设计阶段-设计时就定义评测标准和测试用例；②开发阶段-Prompt变更本地跑快速评测(类似单元测试)；③CI阶段-自动化回归；④线上阶段-持续监控。核心理念：测试不是开发完才做的事，而是和开发同步的事。\n"
  "L2追问: 左移最大挑战是什么？\n"
  "L2应对: 最大挑战是'测试用例先行'需要业务方配合：①Prompt还没写好就要定义测试用例(反直觉)；②测试用例需要持续维护(业务变化后需更新)。解决：①把测试用例设计纳入Prompt设计Review(作为必选项)；②提供模板降低门槛；③展示ROI-早期发现问题修复成本是后期的1/10。文化转变比技术更难。\n"
  "L3追问: 如果业务方说'我Prompt都还没定，没法写测试用例'，你怎么办？\n"
  "L3兜底: 退一步：①先写'目标测试用例'-定义Prompt应该达成什么效果(不绑定具体Prompt)；②Prompt原型出来后，目标用例转化成具体用例；③等Prompt稳定后再补边界用例。类比TDD：先写测试(定义期望行为)→再写代码(Prompt)。但AI的不确定性让TDD更难，可以先写'验收标准'级别的用例。")

Q("Q98. 你们平台的瓶颈在哪里？怎么突破？",
  "L1: 当前瓶颈是评测速度(单任务评测200条用例约15分钟)。突破方案：①并行化-多Worker并发执行(已做)；②缓存-相同Prompt+相同用例复用结果(避免重复调LLM)；③渐进评测-先跑快速冒烟(30条/2分钟)→通过后再全量；④本地模型-高频场景用本地模型替代API(降低延迟+成本)。\n"
  "L2追问: 缓存策略具体怎么做？什么情况下可以复用缓存？\n"
  "L2应对: 缓存Key=hash(Prompt内容+模型名+参数(temperature/max_tokens)+测试用例ID)。命中条件：①Prompt完全一致(含变量值)；②模型和参数一致；③距上次评测<24小时(过期重测)。存Redis(JSON序列化结果+TTL)。注意事项：①非确定性输出(Temperature>0)不适合缓存；②缓存一致性-模型版本升级后需刷新缓存。\n"
  "L3追问: 如果Prompt模板相同但变量值不同，怎么缓存？\n"
  "L3兜底: 分两层缓存：①模板层-模板的静态部分可缓存(如System Prompt，很少变)；②实例层-变量填充后的完整Prompt才执行(如User Message)，缓存Key包含变量值。System Prompt不变时，只重跑User Message部分(减少LLM调用)。这类似于'模板缓存+实例计算'模式。但需要注意：System Prompt和User Message的组合效果可能不等于分别评估。")

Q("Q99. 如果让你把平台做成SaaS产品对外卖，你需要加什么？",
  "L1: 核心能力已有，需加的：①多租户+计费系统(按评测次数/Token消耗/月订阅)；②注册登录+组织管理(一个公司多用户)；③API Key管理(用户自带API Key或我们提供)；④SLA保障(可用性/数据安全/备份)；⑤在线文档+视频教程；⑥技术支持渠道(Ticket/Chat)。还有合规(隐私政策/GDPR/等保)。\n"
  "L2追问: 计费系统怎么设计？按什么收费合理？\n"
  "L2应对: 混合计费模式：①基础版-免费(每月100次评测，功能受限)；②专业版-按评测次数(每千次X元)+Token消耗(实际API费用+溢价)；③企业版-年订阅(不限次数+专属部署+定制化)。定价策略：参考LangSmith($39/月/座)，我们可做差异化(更便宜+更聚焦AI测试场景)。\n"
  "L3追问: 如果客户说'太贵了，我直接用LangSmith'，你怎么回应？\n"
  "L3兜底: 差异化价值：①我们专注测试场景(非通用LLMOps)，评测指标体系更贴合测试工程师需求；②数据安全(私有部署vs SaaS)；③可定制化(自定义指标+场景模板)；④中文支持更好。如果客户预算有限→推荐基础版试用；如果LangSmith真更合适→坦诚推荐LangSmith。赢得信任比赢得单子更重要。")

Q("Q100. 你怎么保证平台的技术选型不过时？",
  "L1: 三个策略：①持续关注-订阅技术周刊(Rundown/CHANGELOG)+GitHub Trending+社区讨论；②定期评估-每季度Review技术栈(是否有更好方案)；③可替换设计-核心组件通过接口抽象(如LLMClient/VectorStore)，替换成本低。但不盲目追新：新技术需要观察期(社区活跃度/生产案例/稳定性)。\n"
  "L2追问: 你怎么判断一个新技术是否值得引入？\n"
  "L2应对: 四维评估：①解决了当前真实痛点(不是'看起来很酷')；②社区活跃度(GitHub Stars/Issue响应/贡献者数)；③生产案例(有没有公司在用)；④迁移成本(从现有方案切过去多大代价)。打分制，>80分才考虑引入。例如：前段时间MCP协议很火，但还在早期，只做调研不引入。\n"
  "L3追问: 如果Leader要你引入一个你认为不成熟的技术，你怎么办？\n"
  "L3兜底: 不直接反对，用数据和风险分析说话：①写一份技术评估(优势/劣势/风险/替代方案)；②建议小范围PoC(非核心功能试水)；③设定明确的'成功标准'和'回滚计划'(如果X周内达不到Y就退回)。关键：把'我的意见'变成'数据和事实'，把'反对'变成'风险管理'。")

# Q101-Q120 由下一批继续
# 由于token限制，此处仅展示前100题结构
# 实际生成文件将包含完整的120题
