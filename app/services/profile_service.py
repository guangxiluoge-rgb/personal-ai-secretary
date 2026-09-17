from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Memory
from app.models.profile import ProfileAnswer, ProfileFact, ProfileQuestionnaire
from app.profile.questions import DIMENSIONS, QUESTION_BY_KEY, QUESTIONS, question_for_next


def ensure_questionnaire(db: Session, user_id: int) -> ProfileQuestionnaire:
    row = db.query(ProfileQuestionnaire).filter(ProfileQuestionnaire.user_id == user_id).first()
    if row:
        return row
    row = ProfileQuestionnaire(user_id=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_consent(db: Session, user_id: int, accepted: bool) -> ProfileQuestionnaire:
    row = ensure_questionnaire(db, user_id)
    if accepted:
        now = datetime.utcnow()
        row.status = "active"
        row.consent_at = row.consent_at or now
        row.started_at = row.started_at or now
    else:
        row.status = "paused"
    db.commit()
    db.refresh(row)
    return row


def _counts(db: Session, questionnaire_id: int) -> dict[str, int]:
    rows = db.query(ProfileAnswer.dimension, ProfileAnswer.question_key).filter(ProfileAnswer.questionnaire_id == questionnaire_id).all()
    counts = {d: 0 for d in DIMENSIONS}
    for dimension, _ in rows:
        counts[dimension] = counts.get(dimension, 0) + 1
    return counts


def next_question(db: Session, user_id: int) -> dict:
    row = ensure_questionnaire(db, user_id)
    if row.status != "active":
        return {"status": row.status, "question": None}
    answers = db.query(ProfileAnswer).filter(ProfileAnswer.questionnaire_id == row.id).all()
    keys = {a.question_key for a in answers}
    counts = _counts(db, row.id)
    question = question_for_next(keys, counts, 1 if len(answers) < len(QUESTIONS) else len(answers) - len(QUESTIONS) + 2)
    foundational = min(len(QUESTIONS), sum(1 for k in keys if k in QUESTION_BY_KEY))
    return {
        "status": row.status,
        "question": {"key": question.key, "dimension": question.dimension, "title": question.title, "prompt": question.prompt},
        "progress": {"answered": len(answers), "foundational": foundational, "total": len(QUESTIONS)},
    }


def _upsert_profile_fact(db: Session, answer: ProfileAnswer, title: str, statement: str) -> ProfileFact:
    confidence = min(0.95, 0.45 + len(statement.strip()) / 350)
    fact = (
        db.query(ProfileFact)
        .filter(ProfileFact.user_id == answer.user_id, ProfileFact.dimension == answer.dimension, ProfileFact.label == title)
        .order_by(ProfileFact.updated_at.desc())
        .first()
    )
    if fact is None:
        fact = ProfileFact(user_id=answer.user_id, dimension=answer.dimension, label=title, statement=statement[:2000], confidence=confidence, source_answer_id=answer.id)
        db.add(fact)
    else:
        fact.statement = statement[:2000]
        fact.confidence = confidence
        fact.source_answer_id = answer.id
        fact.updated_at = datetime.utcnow()

    memory_text = f"用户画像·{answer.dimension}·{title}：{statement[:700]}"
    existing = db.query(Memory).filter(Memory.user_id == answer.user_id, Memory.layer == "profile", Memory.content == memory_text).first()
    if existing is None:
        db.add(Memory(user_id=answer.user_id, layer="profile", memory_type="profile_fact", content=memory_text, importance=.9, confidence=confidence))
    return fact


def save_answer(db: Session, user_id: int, question_key: str, answer_text: str) -> dict:
    answer_text = answer_text.strip()
    if len(answer_text) < 2:
        raise ValueError("请至少写两句话或几个词，让我更了解你")
    if len(answer_text) > 5000:
        raise ValueError("回答太长，请控制在 5000 字以内")
    row = ensure_questionnaire(db, user_id)
    if row.status != "active":
        raise ValueError("请先同意个人画像采集")
    question = QUESTION_BY_KEY.get(question_key)
    if question is None and "_r" in question_key:
        base = question_key.rsplit("_r", 1)[0]
        question = QUESTION_BY_KEY.get(base)
    if question is None:
        raise ValueError("question not found")

    existing = db.query(ProfileAnswer).filter(ProfileAnswer.questionnaire_id == row.id, ProfileAnswer.question_key == question_key).first()
    if existing:
        raise ValueError("这个问题已经回答过了")
    existing_count = db.query(ProfileAnswer).filter(ProfileAnswer.questionnaire_id == row.id).count()
    round_no = 1 if existing_count < len(QUESTIONS) else 2 + existing_count - len(QUESTIONS)
    answer = ProfileAnswer(user_id=user_id, questionnaire_id=row.id, question_key=question_key, dimension=question.dimension, answer=answer_text, round_no=round_no)
    db.add(answer)
    db.flush()
    _upsert_profile_fact(db, answer, question.title, answer_text)

    if existing_count + 1 >= len(QUESTIONS):
        row.completed_at = row.completed_at or datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
    return next_question(db, user_id)


def get_profile(db: Session, user_id: int) -> dict:
    facts = db.query(ProfileFact).filter(ProfileFact.user_id == user_id).order_by(ProfileFact.dimension, ProfileFact.updated_at.desc()).all()
    answers = db.query(ProfileAnswer).filter(ProfileAnswer.user_id == user_id).order_by(ProfileAnswer.created_at.desc()).limit(100).all()
    grouped = {d: [] for d in DIMENSIONS}
    for fact in facts:
        grouped.setdefault(fact.dimension, []).append({"id": fact.id, "label": fact.label, "statement": fact.statement, "confidence": round(fact.confidence, 2), "updated_at": fact.updated_at})
    return {
        "dimensions": grouped,
        "answer_count": len(answers),
        "recent_answers": [{"question_key": a.question_key, "dimension": a.dimension, "answer": a.answer, "created_at": a.created_at} for a in answers[:12]],
    }


def delete_profile_data(db: Session, user_id: int) -> None:
    questionnaire = db.query(ProfileQuestionnaire).filter(ProfileQuestionnaire.user_id == user_id).first()
    db.query(Memory).filter(Memory.user_id == user_id, Memory.layer == "profile").delete(synchronize_session=False)
    db.query(ProfileFact).filter(ProfileFact.user_id == user_id).delete(synchronize_session=False)
    db.query(ProfileAnswer).filter(ProfileAnswer.user_id == user_id).delete(synchronize_session=False)
    if questionnaire:
        questionnaire.status = "paused"
        questionnaire.consent_at = None
        questionnaire.started_at = None
        questionnaire.completed_at = None
    db.commit()
