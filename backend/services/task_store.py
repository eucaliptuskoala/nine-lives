import uuid
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from models.schemas import CatResponse


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class DigitizeTask:
    id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[CatResponse] = None
    error: Optional[str] = None
    owner_id: Optional[str] = None


_tasks: dict[str, DigitizeTask] = {}
_lock = threading.Lock()


def create_task(owner_id: str) -> DigitizeTask:
    task = DigitizeTask(id=str(uuid.uuid4()), owner_id=owner_id)
    with _lock:
        _tasks[task.id] = task
    return task


def get_task(task_id: str) -> Optional[DigitizeTask]:
    with _lock:
        return _tasks.get(task_id)


def update_task(task_id: str, **kwargs):
    with _lock:
        task = _tasks.get(task_id)
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
