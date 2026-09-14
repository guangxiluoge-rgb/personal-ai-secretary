# Personal AI Secretary — 开发与交付文档

## 1. 项目定位

个人 AI 助理后端：统一承载身份认证、长期记忆、AI 对话、健康管理、健康趋势、周度生活方式计划、订阅权益、微信支付、支付宝、Stripe，以及后台配置。

目标原则：

- AI 是执行层，用户画像/记忆/健康事实是数据层。
- 健康图片优先本地筛选，只有确认后的相关图片进入 AI。
- 同一图片通过 SHA-256 去重并只分析一次。
- 后续健康问答优先使用结构化 Health Facts + Trends，减少重复图片 token。
- 健康模块输出健康管理与风险提示，不把模型输出包装成未经验证的临床诊断。
- 支付回调必须验签、幂等，权益以服务端状态为准。
- AI Provider 采用可替换的抽象，不绑定单一模型厂商。

## 2. 技术栈

- Python 3.12
- FastAPI
- SQLAlchemy 2
- PostgreSQL / psycopg
- Alembic
- Redis + Celery（异步任务基础设施）
- httpx
- Stripe SDK
- cryptography
- PyJWT + Argon2
- pytest + Ruff

## 3. 代码结构

```text
app/
  api/                 HTTP API
    admin.py           后台登录/配置
    ai.py              AI 对话
    auth.py            注册/登录
    billing.py         支付与订阅
    health.py          健康图片/记录/趋势
    memory.py          记忆接口
  core/                配置、安全
  models/              数据模型
  services/
    ai_gateway.py      AI Provider 抽象
    ai_provider.py     OpenAI-compatible Provider
    gemini_vision_provider.py Gemini 图片理解 Provider
    memory_service.py  5 层记忆
    health_classifier.py 本地零 token 分类
    health_facts.py    Health Facts/Trends
    health_prompt.py   健康分析提示词与 JSON schema
    health_analysis.py 图片分析任务
    health_service.py  健康记录与风险告警
    wellness_service.py 周度生活方式计划
    entitlement_service.py 权益生命周期
    admin_service.py   后台运行时配置
migrations/            Alembic migrations
admin/                 后台页面
 tests/                自动化测试
```

## 4. 记忆系统

当前采用 5 层记忆策略：

| 层 | 默认 TTL | 用途 |
|---|---:|---|
| temporary | 1 天 | 当前短期上下文 |
| working | 7 天 | 当前任务 |
| episodic | 90 天 | 重要历史事件 |
| semantic/profile | 长期 | 稳定偏好、用户画像 |
| system | 配置级 | 系统规则 |

读取时按相关度、层级权重、时间衰减排序，并限制上下文字符数；重复内容先去重。

## 5. 健康图片完整链路

### 5.1 Gallery Intake

浏览器不能在没有用户授权的情况下静默扫描完整系统相册。因此客户端应采用：

1. 用户点击健康相册入口。
2. 调用 iOS PhotoKit / Android Photo Picker。
3. 本地执行文件名、元数据、截图特征、OCR、关键词分类。
4. 仅把候选结果展示给用户确认。
5. 只上传确认后的健康相关图片。
6. 服务端计算 SHA-256。
7. 相同 hash 不重复创建分析任务。

本地筛选阶段原则上为 0 AI token。

### 5.2 分类

`health_classifier.py` 对 OCR 文本和文件信息识别：

- wearable
- medical_report
- tongue
- face
- unknown

分类不是医疗诊断，只用于决定是否进入后续健康分析链路。

### 5.3 分析

确认图片进入 `HealthAnalysisJob` 后：

```text
Upload
  -> SHA-256 dedupe
  -> HealthAnalysisJob
  -> background analysis
  -> visual/generic AI analysis
  -> structured JSON
  -> HealthRecord
  -> HealthMetric
  -> HealthAlert
  -> AIUsage
```

每张图片只分析一次；后续问答使用结构化事实，而不是重新发送原图。

### 5.4 面部 / 舌象视觉模型

`face` 与 `tongue` 图片进入专用 `GeminiVisionProvider`。Gemini Interactions API 支持图片输入与 JSON Structured Output，因此服务端可以直接把视觉结果约束成结构化字段。citeturn682417search1turn682417search3

视觉分析重点：

- 面部：只记录照片中可见的皮肤/区域表现、对称性等客观特征，不推断性格、命运、财富等非医学信息。
- 舌象：记录舌体颜色、舌苔、湿润度、裂纹、齿痕、斑点等可见特征。
- 输出：`observations`、`metrics`、`risk_level`、`flags`。
- 图像质量不够时降低 confidence，并要求重新拍摄。
- 视觉模型只能做健康观察和风险评估，不能仅凭一张脸或舌头照片确定疾病诊断。

## 6. Health Facts / Trends

`Health Facts` 是图片分析后的结构化健康事实，例如：

- 心率
- 睡眠时长
- 步数
- 血氧
- 体重
- 血压
- 用户确认的报告/OCR事实
- 面部/舌象视觉观察

`Trends` 从历史事实计算变化方向，用于后续 AI 上下文。

上下文默认只取最近 7–14 天的有限事实，并设置最大事实条数和最大字符数，防止健康历史无限膨胀导致 token 浪费。

## 7. 健康风险告警

风险等级：

- `normal`
- `watch`
- `urgent`

模型输出非法风险等级时降级为 `watch`，避免把未知值当作正常。

`urgent` 会创建 `HealthAlert`，交给平台后续人工/专业复核流程。

## 8. 健康 AI 分析

当前有两条 Provider 路线：

1. `OpenAICompatibleProvider`：负责通用 AI 对话、可兼容的文本/健康数据分析。
2. `GeminiVisionProvider`：专门负责 `face/tongue` 图片理解。

需要配置：

- 通用 AI：`AI_API_URL` / `AI_API_KEY` / `AI_MODEL`
- Gemini Vision：`GEMINI_API_KEY` / `GEMINI_MODEL`

系统通过 `health_prompt.py` 强制结构化 JSON 输出，并要求模型：

- 只做健康管理/风险提示；
- 不自行诊断疾病；
- 不开具处方；
- 数据不足时采用保守建议；
- 返回 observations / metrics / flags / risk_level 等结构化字段。

## 9. 周度健康管理计划

`WeeklyWellnessPlan` 按自然周缓存。

计划覆盖：

- 饮食 / 食疗
- 运动
- 睡眠
- 恢复
- 冥想
- 泡澡 / 泡脚
- 按摩 / 拉伸
- 芳香疗法
- 音乐疗法
- 安全注意事项

生成前只向模型发送压缩后的 Health Context，并计算 `source_context_hash`。同一周、同一健康上下文不会重复调用模型；健康事实发生变化或显式 force 时才重新生成。

## 10. Token 控制策略

核心规则：

```text
本地相册筛选       = 0 token
OCR/关键词分类     = 0 token
SHA-256 去重       = 0 token
已分析图片再次使用 = 0 次重复图片分析
后续问答           = Health Facts + Trends
上下文             = 有上限的 compact JSON
```

这套策略的目标不是单次请求省几个 token，而是让用户使用数月后上下文仍然可控。

## 11. AI Gateway

所有模型调用通过 `AIGateway`。

当前 Provider：

- `OpenAICompatibleProvider`
- `GeminiVisionProvider`

接口核心字段：

- user_id
- messages
- model
- temperature
- max_tokens
- metadata

图片 Provider 通过 `metadata.image_path` 接收已经确认的本地图片，不让前端直接把原图重复塞进后续聊天上下文。

返回：

- text
- provider
- model
- input_tokens
- output_tokens
- request_id

AI 调用应记录 `AIUsage`，便于成本统计和后续限流。

## 12. 权益系统

`Entitlement` 负责用户功能有效期。

核心操作：

- grant：授予/覆盖权益
- extend：在当前有效期之后继续延长
- revoke：撤销
- has_feature：检查当前是否有效

月度订阅的续期必须使用 `extend` 语义，不能把已有有效期重置成从当前时间重新计算的一个月。

## 13. 支付系统

支持：

- 微信支付
- 支付宝
- Stripe

共同原则：

1. 创建订单。
2. 跳转支付渠道。
3. 渠道 webhook/callback。
4. 验签。
5. 校验订单金额和状态。
6. 幂等完成订单。
7. 发放/延长权益。

### Stripe

需要覆盖：

- Checkout Session
- payment success
- invoice paid / recurring renewal
- subscription cancellation
- payment failure

取消订阅不应无条件立即抹掉已经付费的剩余有效期；服务端应以 entitlement.expires_at 为最终可用期限。

### 微信/支付宝

回调必须验证平台签名；敏感回调数据解密后才能进入订单完成逻辑。重复回调不能重复发放权益。

## 14. 后台配置

`/admin` 提供后台配置入口。

配置包括：

- 通用 AI Provider
- Gemini Vision
- Stripe
- 微信支付
- 支付宝
- 系统参数

生产环境密钥不得提交 Git。后台配置写入 `SystemSetting`，服务端运行时读取。

## 15. 数据库迁移

当前 migration 顺序：

```text
0001_initial.py
0002_health_jobs.py
0003_admin_settings.py
0004_health_gallery_metadata.py
0005_weekly_wellness_plans.py
0006_stripe_subscription_mapping.py
0007_remove_antfu_settings.py
```

部署数据库时：

```bash
alembic upgrade head
```

任何新增字段/表必须新增 migration，不允许直接依赖 `Base.metadata.create_all()` 修改生产数据库。

## 16. 本地运行

安装：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

配置环境变量后：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

健康检查：

```text
GET /health
```

后台：

```text
GET /admin
```

## 17. CI

GitHub Actions 当前执行：

```bash
pip install -r requirements.txt
python -m compileall app migrations
ruff check app migrations tests
pytest -q
```

## 18. 测试重点

必须持续覆盖：

- Health Facts 趋势计算
- JSON 压缩
- 周度计划 schema/normalize
- 周度计划 context hash 缓存
- 健康图片 hash 去重
- 风险等级与 urgent alert
- Gemini Vision MIME / JSON 响应解析
- face/tongue Provider 路由
- entitlement extend
- 支付回调幂等
- 金额校验
- AI provider 未配置时的明确错误

## 19. 生产部署检查

### 必须配置

```text
DATABASE_URL
JWT secret
ADMIN_SECRET
AI_API_URL
AI_API_KEY
AI_MODEL
GEMINI_API_KEY
GEMINI_MODEL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
WECHAT_* credentials
ALIPAY_* credentials
```

实际变量名以 `app/core/config.py` 为准。

### 必须完成

- PostgreSQL 可用
- Redis 可用（启用异步任务时）
- HTTPS
- Stripe webhook URL
- 微信支付回调 URL
- 支付宝回调 URL
- 图片对象存储/持久化存储
- 日志与告警
- 数据库备份
- 健康数据访问权限控制
- 生产密钥不进 Git

## 20. 当前交付边界

本版本聚焦个人 AI 助理核心链路：认证、AI、记忆、健康管理、健康图片 intake、Health Facts/Trends、面部/舌象视觉分析、周度 wellness、订阅权益、三支付渠道和后台配置。

商城、社交治理等未纳入当前交付，不在没有明确需求的情况下扩张范围。

## 21. 上线前最后一道原则

CI 通过 ≠ 第三方服务已经开通。

代码层可以完成并验证，但真实支付仍需要运营方提供正式商户凭证、回调域名及生产环境配置；面部/舌象视觉分析则需要配置 Gemini API Key 和正式视觉模型。视觉结果必须定位为健康观察与风险评估，不能把模型结果直接当作医疗确诊。
