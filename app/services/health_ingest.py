from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeResult:
    image_type: str
    confidence: float
    reasons: tuple[str, ...]
    should_send_to_ai: bool


KEYWORDS = {
    "wearable": (
        "心率", "静息", "血氧", "spo2", "睡眠", "深睡", "浅睡", "步数", "卡路里",
        "活动", "训练", "体温", "血压", "hr", "ecg", "手环", "手表", "apple watch",
        "fitbit", "garmin", "xiaomi watch", "mi band",
    ),
    "medical_report": (
        "体检", "检验", "化验", "报告", "血常规", "尿常规", "肝功能", "肾功能",
        "血糖", "葡萄糖", "胆固醇", "甘油三酯", "血红蛋白", "白细胞", "红细胞",
        "检验结果", "参考范围", "reference range", "laboratory", "lab report",
    ),
    "tongue": ("舌象", "舌诊", "舌头", "tongue"),
    "face": ("面诊", "面部", "人脸", "脸部", "face"),
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def classify_candidate(filename: str = "", ocr_text: str = "") -> IntakeResult:
    """Classify gallery candidates without calling an LLM.

    OCR is optional. The function deliberately returns unknown when evidence is weak;
    false positives are more dangerous than asking the user to confirm a candidate.
    """
    name = _normalize(filename)
    text = _normalize(ocr_text)
    combined = f"{name} {text}".strip()

    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    for image_type, words in KEYWORDS.items():
        hits = [word for word in words if _normalize(word) in combined]
        if hits:
            scores[image_type] = min(0.95, 0.45 + 0.08 * len(hits))
            reasons[image_type] = hits[:4]

    if not scores:
        return IntakeResult("unknown", 0.0, (), False)

    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]
    competing = sorted(scores.values(), reverse=True)
    if len(competing) > 1 and competing[0] - competing[1] < 0.16:
        return IntakeResult("unknown", 0.0, ("multiple health categories matched",), False)

    return IntakeResult(
        best_type,
        confidence,
        tuple(reasons[best_type]),
        confidence >= 0.60,
    )


def build_token_saving_plan(candidate_count: int, confirmed_count: int, already_analyzed_count: int) -> dict:
    """Return a deterministic ingestion plan; no model call is needed."""
    return {
        "candidate_count": max(0, candidate_count),
        "confirmed_count": max(0, confirmed_count),
        "already_analyzed_count": max(0, already_analyzed_count),
        "ai_image_calls": max(0, confirmed_count - already_analyzed_count),
        "strategy": "local_filter_then_hash_dedupe_then_single_analysis",
        "send_original_image_again": False,
        "send_structured_facts_to_followup_ai": True,
    }
