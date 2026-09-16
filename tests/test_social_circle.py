from datetime import datetime, timedelta

from app.models.social_circle import SocialCircle, SocialCircleEvent, SocialCircleMember, SocialCircleTopic


def test_social_circle_fields():
    circle = SocialCircle(user_id=7, name="老同学", visibility="private", status="active")
    assert circle.name == "老同学"
    assert circle.visibility == "private"
    assert circle.status == "active"


def test_social_circle_member_fields():
    member = SocialCircleMember(circle_id=1, person_id=2, role="member", status="active")
    assert member.role == "member"
    assert member.status == "active"


def test_social_circle_topic_and_event_fields():
    topic = SocialCircleTopic(circle_id=1, title="行业交流", tags="行业,项目")
    event = SocialCircleEvent(circle_id=1, topic_id=3, event_type="message", summary="分享了项目进展", occurred_at=datetime.utcnow() - timedelta(days=1))
    assert topic.title == "行业交流"
    assert event.event_type == "message"
