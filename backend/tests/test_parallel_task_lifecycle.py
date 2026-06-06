from __future__ import annotations

import time

from generation.harness.task_manager import TaskManager


def _executor(task) -> tuple[str, dict]:
    if "slow" in task.description:
        time.sleep(0.2)
    else:
        time.sleep(0.05)
    return f"done:{task.description}", {"kind": task.subagent_type}


def test_task_lifecycle_background_and_await() -> None:
    manager = TaskManager(executor=_executor)
    task = manager.create_task(
        subagent_type="general",
        description="slow-work",
        prompt="do work",
        background=True,
    )
    assert task.status == "running"

    done = manager.await_task(task.task_id, timeout_ms=1500)
    assert done.status == "completed"
    assert done.result_text == "done:slow-work"
    assert done.result_payload == {"kind": "general"}


def test_parallel_tasks_complete_concurrently() -> None:
    manager = TaskManager(executor=_executor)
    start = time.time()
    t1 = manager.create_task("general", "slow-a", "p1", background=True)
    t2 = manager.create_task("general", "slow-b", "p2", background=True)

    manager.await_task(t1.task_id, timeout_ms=1500)
    manager.await_task(t2.task_id, timeout_ms=1500)
    elapsed = time.time() - start

    # Each task sleeps 0.2s; serial would be around 0.4s.
    assert elapsed < 0.35


def test_cancel_task_marks_cancelled() -> None:
    manager = TaskManager(executor=_executor)
    task = manager.create_task("general", "slow-cancel", "p", background=True)
    cancelled = manager.cancel_task(task.task_id)
    assert cancelled is True
    status = manager.get_task_status(task.task_id, wait=False)
    assert status == "cancelled"
