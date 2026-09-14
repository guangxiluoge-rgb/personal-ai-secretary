from __future__ import annotations

import json


def build_health_analysis_prompt(image_type: str, extracted_text: str, context_json: str) -> list[dict]:
    if image_type in {"face", "tongue"}:
        return build_visual_health_analysis_prompt(image_type, extracted_text, context_json)

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
        "observations": [],
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


def build_visual_health_analysis_prompt(image_type: str, extracted_text: str, context_json: str) -> list[dict]:
    body_target = "面部照片" if image_type == "face" else "舌象照片"
    focus = (
        "观察面部对称性、皮肤颜色与可见皮肤表现、眼周/唇周等区域，仅记录照片中可见现象；"
        "不要从面部外观推断性格、命运、财富、年龄等非医学事实。"
        if image_type == "face"
        else "观察舌体颜色、舌苔颜色与厚薄、湿润度、裂纹、齿痕、斑点等可见特征；"
        "不要把舌象单独当作疾病确诊依据。"
    )
    system = (
        f"你是健康视觉分析助手，负责分析用户提交的{body_target}。"
        "先进行客观视觉观察，再做保守的健康风险评估。"
        "只报告照片中可以合理观察到的特征，不补造不可见信息。"
        f"重点：{focus}"
        "健康风险评估不是临床诊断，不得声称仅凭图片确诊疾病或替代专业医生检查。"
        "如图像模糊、光线异常、角度不合适或信息不足，降低 confidence，并明确说明需要复拍。"
        "输出严格 JSON。"
    )
    schema = {
        "image_type": image_type,
        "summary": "客观、简洁的视觉观察与健康管理摘要",
        "risk_level": "normal|watch|urgent",
        "observations": ["可见的客观特征"],
        "metrics": [{"name": "特征名", "value": "观察值", "unit": "单位或空字符串", "confidence": 0.0}],
        "flags": [{"severity": "watch|urgent", "message": "风险提示与复查建议"}],
    }
    user = {
        "task": "分析图片并生成结构化健康视觉记录。对不可靠的医学推断宁可返回低置信度，也不要给出确定性诊断。",
        "image_type": image_type,
        "ocr_text": extracted_text[:12000],
        "recent_context": context_json[:5000],
        "output_schema": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))}]
