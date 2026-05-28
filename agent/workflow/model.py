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
                {"id": s.id, "title": s.title, "type": s.type, "status": s.status, "notes": s.notes}
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        steps = [WorkflowStep(**s) for s in data.get("steps", [])]
        return cls(
            thread_id=data["thread_id"],
            task_type=data["task_type"],
            title=data["title"],
            steps=steps,
        )
