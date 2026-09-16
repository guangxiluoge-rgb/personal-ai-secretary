from datetime import datetime

from app.models.task import LifeTask


def test_life_task_fields():
    due_at = datetime(2026, 9, 20, 10, 30)
    task = LifeTask(
        user_id=1,
        title="联系老同学",
        task_type="follow_up",
        priority="high",
        status="open",
        due_at=due_at,
        source="manual",
        notes="确认周末聚会",
    )
    assert task.title == "联系老同学"
    assert task.task_type == "follow_up"
    assert task.priority == "high"
    assert task.status == "open"
    assert task.due_at == due_at


def test_life_task_completed_at_can_be_recorded():
    task = LifeTask(user_id=1, title="完成会议行动项", status="completed")
    task.completed_at = datetime(2026, 9, 20, 12, 0)
    assert task.status == "completed"
    assert task.completed_at is not None
