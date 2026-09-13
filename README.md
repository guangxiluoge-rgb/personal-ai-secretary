# Personal AI Secretary / AI Life OS

个人 AI 助理 MVP 后端。目标是让用户拥有长期记忆、AI 对话、健康数据后台分析、订阅支付和可运营的管理后台。

## 已落地
- FastAPI + PostgreSQL + Alembic
- JWT 用户注册/登录
- 五层记忆：temporary / working / episodic / semantic / profile；按层 TTL、去重和上下文召回
- AI Gateway + 可配置的 OpenAI-compatible Provider
- AI token 用量记录
- 健康图片安全上传、后台分析任务状态、风险告警数据模型
- Stripe Checkout + webhook 幂等基础
- Entitlement 权益模型
- 管理员登录与 `/admin` 管理界面
- **API Key、模型、Stripe、套餐金额等均可在管理后台修改，不需要改代码**
- Docker Compose + CI 基础

## 启动

```bash
cp .env.example .env
# 编辑 .env，至少设置 JWT_SECRET、ADMIN_BOOTSTRAP_EMAIL、ADMIN_BOOTSTRAP_PASSWORD

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
- 蚂蚁阿福 API 地址 / API Key / 模型名
- Stripe Secret / Webhook Secret
- Pro / Health Pro / Premium 的 Stripe Price ID
- 三档套餐价格（最小货币单位）
- 前端 CORS 来源

敏感配置在后台只显示掩码；数据库配置优先于环境变量，因此运营人员可以直接调整运行参数。

## 健康模块边界
健康图片会先进入后台任务队列模型；具体“蚂蚁阿福”视觉 API 的 endpoint、签名和字段必须以官方接口文档为准，本项目不会虚构第三方 API 协议。健康输出定位为健康管理、风险提示和生活方式建议，不替代医疗诊断。

## 下一阶段
- 真正的异步任务 Worker（Redis/Celery）
- 蚂蚁阿福官方视觉适配器（拿到官方接口参数后接入）
- 健康风险规则与周度 wellness engine
- Stripe 订阅生命周期完整同步
- 正式用户端 Web/App
- 审计日志、限流、敏感数据加密与生产部署
