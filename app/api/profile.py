from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.services.profile_service import delete_profile_data, ensure_questionnaire, get_profile, next_question, save_answer, set_consent

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ConsentIn(BaseModel):
    accepted: bool


class AnswerIn(BaseModel):
    question_key: str = Field(min_length=2, max_length=80)
    answer: str = Field(min_length=2, max_length=5000)


@router.get("/state")
def profile_state(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return next_question(db, user_id)


@router.post("/consent")
def profile_consent(data: ConsentIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    row = set_consent(db, user_id, data.accepted)
    return {"status": row.status, "consent": bool(row.consent_at), "started_at": row.started_at}


@router.post("/answer")
def profile_answer(data: AnswerIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        return save_answer(db, user_id, data.question_key, data.answer)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/me")
def profile_me(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    questionnaire = ensure_questionnaire(db, user_id)
    return {"questionnaire": {"status": questionnaire.status, "consent": bool(questionnaire.consent_at), "started_at": questionnaire.started_at, "completed_at": questionnaire.completed_at}, "profile": get_profile(db, user_id)}


@router.delete("/me", status_code=204)
def profile_delete(response: Response, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    delete_profile_data(db, user_id)
    response.status_code = 204
    return None
