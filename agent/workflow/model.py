from dataclasses import dataclass, field
from typing import Literal

StepType = Literal["auto", "semi_auto", "manual"]
StepStatus = Literal["pending", "running", "waiting", "done", "error", "skipped"]


@dataclass
class WorkflowStep:
    id: str
    title: str
    type: StepType = "auto"
    status: StepStatus = "pending"
    notes: str = ""
    max_retry: int = 0


@dataclass
class Workflow:
    thread_id: str
    task_type: str
    title: str
    steps: list = field(default_factory=list)  # list[WorkflowStep]

    def to_dict(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "task_type": self.task_type,
            "title": self.title,
            "steps": [
                {
                    "id": s.id,
                    "title": s.title,
                    "type": s.type,
                    "status": s.status,
                    "notes": s.notes,
                    "max_retry": s.max_retry,
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                id=s["id"],
                title=s["title"],
                type=s.get("type", "auto"),
                status=s.get("status", "pending"),
                notes=s.get("notes", ""),
                max_retry=s.get("max_retry", 0),
            ))
        return cls(
            thread_id=data["thread_id"],
            task_type=data["task_type"],
            title=data["title"],
            steps=steps,
        )
