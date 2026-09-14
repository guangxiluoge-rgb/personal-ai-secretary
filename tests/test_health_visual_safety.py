from app.services.health_analysis import _clamp_confidence
from app.services.health_prompt import build_visual_health_analysis_prompt


def test_visual_prompt_is_non_diagnostic_for_face_and_tongue():
    face = build_visual_health_analysis_prompt("face", "", "{}")
    tongue = build_visual_health_analysis_prompt("tongue", "", "{}")
    face_text = face[0]["content"] + face[1]["content"]
    tongue_text = tongue[0]["content"] + tongue[1]["content"]
    assert "不得声称仅凭图片确诊疾病" in face_text
    assert "不得声称仅凭图片确诊疾病" in tongue_text
    assert "舌象单独当作疾病确诊依据" in tongue_text or "不得声称仅凭图片确诊疾病" in tongue_text
    assert "image_quality" in face_text
    assert "analysis_confidence" in tongue_text


def test_confidence_is_clamped_to_safe_range():
    assert _clamp_confidence(-1) == 0.0
    assert _clamp_confidence(0.75) == 0.75
    assert _clamp_confidence(9) == 1.0
    assert _clamp_confidence("invalid") == 0.0
