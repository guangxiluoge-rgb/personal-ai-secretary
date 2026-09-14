from __future__ import annotations

import json


def build_health_analysis_prompt(image_type: str, extracted_text: str, context_json: str) -> list[dict]:
    system = (
        "你是健康数据结构化助手。只处理用户明确提交的健康图片。"
        "输出严格 JSON，不写长篇解释，不猜测图片中不可见的数据。"
        "健康建议仅用于健康管理和风险提示，不作疾病诊断。"
        "如果数据不清晰，返回 null 或低 confidence。"
    )
    schema = {
        "image_type": image_type,
        "summary": "string",
        "risk_level": "normal|watch|urgent",
        "metrics": [{"name": "string", "value": "string", "unit": "string", "confidence": 0.0}],
        "flags": [{"severity": "watch|urgent", "message": "string"}],
    }
    user = {
        "task": "从已确认的健康图片中提取结构化数据；如已有 OCR 文本，优先校验并结构化，不重复描述图片。",
        "image_type": image_type,
        "ocr_text": extracted_text[:12000],
        "recent_context": context_json[:5000],
        "output_schema": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))}]
