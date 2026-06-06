from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, Tuple

TaskStatus = Literal["running", "completed", "error", "cancelled"]


@dataclass
class TaskRecord:
    task_id: str
    subagent_type: str
    description: str
    prompt: str
    status: TaskStatus
    created_at: float
    updated_at: float
    result_text: str = ""
    result_payload: dict[str, Any] | None = None
    error: str | None = None
    parent_session_id: str | None = None
    background: bool = False
    resume_task_id: str | None = None


TaskExecutor = Callable[[TaskRecord], Tuple[str, Optional[dict[str, Any]]]]


class TaskManager:
    def __init__(self, executor: TaskExecutor | None = None) -> None:
        self._executor = executor
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def create_task(
        self,
        subagent_type: str,
        description: str,
        prompt: str,
        background: bool = False,
        resume_task_id: str | None = None,
        parent_session_id: str | None = None,
    ) -> TaskRecord:
        now = time.time()
        task = TaskRecord(
            task_id=uuid.uuid4().hex,
            subagent_type=subagent_type,
            description=description,
            prompt=prompt,
            status="running",
            created_at=now,
            updated_at=now,
            background=background,
            resume_task_id=resume_task_id,
            parent_session_id=parent_session_id,
        )
        with self._cond:
            self._tasks[task.task_id] = task

        if background:
            thread = threading.Thread(target=self._execute_task, args=(task.task_id,), daemon=True)
            thread.start()
        else:
            self._execute_task(task.task_id)
        return self.get_task(task.task_id)

    def get_task(self, task_id: str) -> TaskRecord:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Unknown task_id: {task_id}")
            return TaskRecord(**task.__dict__)

    def get_task_status(
        self,
        task_id: str,
        wait: bool = False,
        timeout_ms: int = 0,
    ) -> TaskStatus:
        if wait:
            self.await_task(task_id, timeout_ms=timeout_ms)
        return self.get_task(task_id).status

    def cancel_task(self, task_id: str) -> bool:
        with self._cond:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Unknown task_id: {task_id}")
            if task.status != "running":
                return False
            task.status = "cancelled"
            task.updated_at = time.time()
            self._cond.notify_all()
            return True

    def await_task(self, task_id: str, timeout_ms: int) -> TaskRecord:
        timeout_s = max(0, timeout_ms) / 1000.0
        deadline = time.time() + timeout_s
        with self._cond:
            while True:
                task = self._tasks.get(task_id)
                if task is None:
                    raise KeyError(f"Unknown task_id: {task_id}")
                if task.status in {"completed", "error", "cancelled"}:
                    return TaskRecord(**task.__dict__)
                remaining = deadline - time.time()
                if timeout_ms > 0 and remaining <= 0:
                    return TaskRecord(**task.__dict__)
                self._cond.wait(timeout=None if timeout_ms <= 0 else remaining)

    def _execute_task(self, task_id: str) -> None:
        with self._cond:
            task = self._tasks.get(task_id)
            if task is None or task.status != "running":
                return

        try:
            if self._executor is None:
                result_text, result_payload = "Task completed", {}
            else:
                result_text, result_payload = self._executor(self.get_task(task_id))
        except Exception as exc:
            with self._cond:
                task = self._tasks.get(task_id)
                if task is None or task.status != "running":
                    return
                task.status = "error"
                task.error = str(exc)
                task.updated_at = time.time()
                self._cond.notify_all()
            return

        with self._cond:
            task = self._tasks.get(task_id)
            if task is None or task.status != "running":
                return
            task.status = "completed"
            task.result_text = result_text
            task.result_payload = result_payload
            task.updated_at = time.time()
            self._cond.notify_all()
