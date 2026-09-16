# Personal AI Secretary / AI Life OS

个人 AI 助理 MVP 后端。目标是让用户拥有长期记忆、AI 对话、健康数据后台分析、社交关系管理、订阅支付和可运营的管理后台。

## 已落地
- FastAPI + PostgreSQL + Alembic
- JWT 用户注册/登录
- 五层记忆：temporary / working / episodic / semantic / profile；按层 TTL、去重和上下文召回
- AI Gateway + 可配置的 OpenAI-compatible Provider
- Gemini Vision 面部/舌象健康视觉分析
- AI token 用量记录
- 健康图片本地预筛、SHA-256 去重、安全上传、后台分析任务状态、风险告警
- Health Facts / Trends，以及每周健康参数曲线与综合评估
- 每周健康调理方案：饮食、休息、睡眠、精力、情绪、运动、营养及其他健康管理建议
- 每周报告历史、四周趋势、月度/季度长期健康画像
- 对话长期记录、自动归档、人物/关系事件、会议纪要和防骗风险提醒
- **社交知青圈**：私有圈子、人物成员、兴趣/主题、互动事件、关系提醒、社交简报
- 外部消息统一导入入口：导入内容后复用 Life OS 的归档、记忆和风险检测链路
- Stripe Checkout + webhook 幂等基础
- Entitlement 权益模型
- 管理员登录与 `/admin` 管理界面
- **API Key、模型、Stripe、套餐金额等均可在管理后台修改，不需要改代码**
- 敏感配置加密存储
- 健康原图可配置留存期
- Docker Compose + CI 基础

## 页面
- `/life-os`：对话、归档、关系、防骗、会议
- `/social`：社交知青圈与关系简报
- `/health`：健康接口健康检查
- `/health/gallery`：健康图片
- `/health/history`：健康周报历史
- `/health/long-term`：月度/季度长期健康画像
- `/admin`：运营管理

## 社交知青圈 API
- `POST /api/social/circles`
- `GET /api/social/circles`
- `GET /api/social/circles/{circle_id}`
- `POST /api/social/circles/{circle_id}/members`
- `POST /api/social/circles/{circle_id}/topics`
- `POST /api/social/circles/{circle_id}/events`
- `GET /api/social/people/search`
- `POST /api/social/people/{person_id}/reminders`
- `GET /api/social/reminders`
- `GET /api/social/briefing`
- `POST /api/social/messages/ingest`

社交圈事件绑定既有 `Person / RelationshipEvent`，避免形成两套互不相通的人脉数据库。

## 启动

```bash
cp .env.example .env
# 编辑 .env，至少设置 JWT_SECRET、ADMIN_BOOTSTRAP_EMAIL、ADMIN_BOOTSTRAP_PASSWORD
# 生产环境还必须设置 SETTINGS_ENCRYPTION_KEY

docker compose up --build
```

首次初始化管理员：

```text
POST http://localhost:8000/api/admin/bootstrap
```

然后打开：

```text
http://localhost:8000/admin
```

## 后台可调整
- 通用 AI API / API Key / 模型名
- Gemini Vision API Key / 模型名
- Stripe Secret / Webhook Secret
- Pro / Health Pro / Premium 的 Stripe Price ID
- 三档套餐价格（最小货币单位）
- 微信支付 / 支付宝配置
- 前端 CORS 来源
- 健康原图留存天数

敏感配置在后台只显示掩码；数据库配置优先于环境变量，因此运营人员可以直接调整运行参数。

## 健康模块边界
健康图片先进行本地预筛和用户确认，再上传并分析。面部/舌象分析使用 Gemini Vision，输出定位为客观视觉观察、健康管理和风险提示，不从照片推断性格、命运等内容，也不替代医疗诊断。健康数据会沉淀为结构化 Facts / Trends；后续问答优先使用结构化数据，减少原图重复调用。

## 每周健康报告
每周将本周全部结构化健康参数整理为时间序列和曲线数据，并统计风险等级；随后生成综合评估与调理建议，覆盖饮食、休息、睡眠、精力、情绪、运动、营养和其他健康相关事项。

定期任务入口：

```bash
python scripts/generate_weekly_health_reports.py
```

API：
- `GET /api/health/weekly-report`
- `GET /api/health/weekly-report/curves`
- `POST /api/health/weekly-report/generate`

详细说明见 `docs/WEEKLY_HEALTH_REPORT.md`。
