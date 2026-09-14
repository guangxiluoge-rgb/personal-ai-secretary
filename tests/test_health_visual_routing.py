from app.services.health_prompt import build_health_analysis_prompt


def test_face_uses_visual_health_prompt():
    messages = build_health_analysis_prompt("face", "", "{}")
    text = " ".join(item["content"] for item in messages)
    assert "照片中可见" in text
    assert "性格、命运、财富" in text


def test_tongue_uses_visual_health_prompt():
    messages = build_health_analysis_prompt("tongue", "", "{}")
    text = " ".join(item["content"] for item in messages)
    assert "舌体颜色" in text
    assert "不要把舌象单独当作疾病确诊依据" in text
