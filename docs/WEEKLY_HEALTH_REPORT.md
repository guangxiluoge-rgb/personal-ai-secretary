# 每周健康报告

系统每周对用户在本周产生的结构化健康数据做一次汇总，生成参数曲线、趋势评估和生活方式调理建议。

## 汇总范围

周报读取 `health_metrics` 和 `health_records`，按参数名称生成时间序列。数值参数提供曲线点；文本型观察保留原始值，避免强行数字化。风险等级同时统计 `normal / watch / urgent`。

## 调理域

每周报告固定覆盖：饮食、休息、睡眠、精力、情绪、运动、营养、其他健康相关调理，以及安全注意事项。

## AI 与规则兜底

AI 只负责综合评估和个性化建议；曲线和原始参数由后端确定性生成。AI 未配置或调用失败时，系统仍生成基础周报，不会因为 AI 不可用导致健康数据丢失。

## 定期执行

部署环境每周执行一次：

```bash
python scripts/generate_weekly_health_reports.py
```

建议将该脚本加入现有 cron / Celery Beat / Kubernetes CronJob。脚本按活跃用户批量生成当前周报，并对未变化的数据幂等复用已有报告。

## API

- `GET /api/health/weekly-report`：当前周完整报告。
- `GET /api/health/weekly-report/curves`：当前周曲线数据，前端可直接用于折线图。
- `POST /api/health/weekly-report/generate`：当前用户立即生成/刷新本周报告。

周报属于健康管理和趋势观察，不作为疾病诊断。出现急性或严重症状时，应结合实际症状及时联系专业医疗人员。
