from __future__ import annotations

import re


TYPE_KEYWORDS = {
    "wearable": ("心率", "静息", "步数", "睡眠", "深睡", "浅睡", "血氧", "spo2", "hr", "bpm", "watch", "fitbit", "garmin"),
    "medical_report": ("检验", "检查", "报告", "血常规", "白细胞", "红细胞", "血红蛋白", "血糖", "葡萄糖", "胆固醇", "alt", "ast", "参考范围"),
    "tongue": ("舌象", "舌苔", "舌质"),
    "face": ("面诊", "面部", "脸部"),
}


def classify_text(text: str, filename: str = "") -> dict:
    haystack = f"{filename} {text}".lower()
    scores = {
        kind: sum(1 for keyword in keywords if keyword.lower() in haystack)
        for kind, keywords in TYPE_KEYWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_kind, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score == 0:
        return {"image_type": "unknown", "confidence": 0.0, "token_cost": 0}
    confidence = min(0.98, 0.55 + best_score * 0.1 + max(0, best_score - second_score) * 0.08)
    if best_score == second_score:
        return {"image_type": "unknown", "confidence": round(confidence * 0.7, 2), "token_cost": 0}
    return {"image_type": best_kind, "confidence": round(confidence, 2), "token_cost": 0}


def normalize_ocr_text(text: str, max_chars: int = 12000) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_chars]
