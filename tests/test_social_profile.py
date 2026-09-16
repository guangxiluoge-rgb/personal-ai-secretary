from datetime import datetime, timedelta

from app.models import Person, RelationshipEvent


def test_social_profile_endpoint(client, auth_headers, db_session):
    person = Person(user_id=auth_headers["user_id"], name="测试对象", relationship_type="partner")
    db_session.add(person)
    db_session.commit()
    db_session.refresh(person)
    db_session.add(RelationshipEvent(user_id=auth_headers["user_id"], person_id=person.id, event_type="interaction", summary="讨论项目与下一步安排", created_at=datetime.utcnow() - timedelta(days=2)))
    db_session.commit()
    response = client.get(f"/api/social/people/{person.id}/profile", headers=auth_headers["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["person"]["name"] == "测试对象"
    assert body["relationship"]["score"] >= 0
    assert body["timeline"][0]["summary"] == "讨论项目与下一步安排"
