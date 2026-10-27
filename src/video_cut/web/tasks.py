"""进程内任务执行器：单任务互斥 + 内存状态 + SSE 订阅广播。

任意时刻最多一个后台任务（pipeline 全是阻塞调用：ffmpeg subprocess、
云 API 轮询），用一把全局锁挡住并发触发。任务状态迁移（pending →
running → done/failed/skipped）广播给所有 SSE 订阅者。server 重启 =
任务状态清零，产物本身仍在盘上（见 spec 07-web-ui Out of Scope）。
"""

from __future__ import annotations

import itertools
import json
import queue
import threading
import traceback
import uuid
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass

# 失败时展示给用户的错误摘要长度（异常消息尾部）。
ERROR_TAIL_LENGTH = 500

TaskWork = Callable[[], str]


@dataclass(frozen=True)
class TaskState:
    """一个后台任务的对外状态快照。"""

    task_id: str
    stem: str
    step: str
    status: str  # pending | running | done | failed | skipped
    detail: str = ""
    error: str = ""


class TaskBusyError(Exception):
    """已有任务在跑，新触发被拒绝（HTTP 层映射为 409）。"""


class TaskRunner:
    """全局单任务执行器；状态存内存 dict，迁移时广播给订阅者。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskState] = {}
        self._subscribers: list[queue.Queue[str | None]] = []
        self._counter = itertools.count(1)

    def acquire(self) -> None:
        """占住任务锁（测试与触发端点共用；不配对 release 会挡住后续任务）。"""
        if not self._lock.acquire(blocking=False):
            raise TaskBusyError("another task is already running")

    def release(self) -> None:
        """放开任务锁。"""
        self._lock.release()

    def try_start(
        self, stem: str, step: str, work: TaskWork
    ) -> TaskState:
        """尝试启动一个后台任务；锁被占用时抛 TaskBusyError。"""
        if not self._lock.acquire(blocking=False):
            raise TaskBusyError("another task is already running")
        task_id = f"task-{next(self._counter)}-{uuid.uuid4().hex[:8]}"
        state = TaskState(task_id=task_id, stem=stem, step=step, status="pending")
        self._tasks[task_id] = state
        self._broadcast("task", json.dumps(asdict(state), ensure_ascii=False))
        thread = threading.Thread(
            target=self._run, args=(task_id, work), daemon=True
        )
        thread.start()
        return state

    def _run(self, task_id: str, work: TaskWork) -> None:
        """任务体：状态迁移广播给订阅者；锁无论如何都会释放。"""
        try:
            self._transition(task_id, "running")
            try:
                detail = work()
            except Exception as error:
                tail = traceback.format_exception_only(error)[-1].strip()
                self._transition(task_id, "failed", error=tail[-ERROR_TAIL_LENGTH:])
            else:
                status = "skipped" if detail.startswith("skipped") else "done"
                self._transition(task_id, status, detail=detail)
        finally:
            self._lock.release()

    def _transition(
        self, task_id: str, status: str, detail: str = "", error: str = ""
    ) -> None:
        current = self._tasks[task_id]
        updated = TaskState(
            task_id=current.task_id,
            stem=current.stem,
            step=current.step,
            status=status,
            detail=detail or current.detail,
            error=error,
        )
        self._tasks[task_id] = updated
        self._broadcast("task", json.dumps(asdict(updated), ensure_ascii=False))

    def snapshot(self) -> list[TaskState]:
        """全部任务状态的一致快照（SSE 初始推送用）。"""
        return list(self._tasks.values())

    def latest_for_stem(self, stem: str) -> TaskState | None:
        """某个视频最近一次任务的状态；没有则 None。"""
        for task_id in reversed(list(self._tasks)):
            state = self._tasks[task_id]
            if state.stem == stem:
                return state
        return None

    def tasks_for_stem(self, stem: str) -> list[TaskState]:
        """某个视频的全部任务，按启动顺序。"""
        return [s for s in self._tasks.values() if s.stem == stem]

    def is_busy(self) -> bool:
        """是否有任务持有锁（用于详情页禁用触发按钮）。"""
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True

    def subscribe(self) -> Iterator[queue.Queue[str | None]]:
        """注册一个 SSE 订阅队列；迭代结束（生成器关闭）时自动注销。"""
        subscriber: queue.Queue[str | None] = queue.Queue()
        self._subscribers.append(subscriber)
        try:
            yield subscriber
        finally:
            self._subscribers.remove(subscriber)

    def _broadcast(self, event: str, data: str) -> None:
        for subscriber in self._subscribers:
            subscriber.put(f"event: {event}\ndata: {data}\n\n")
