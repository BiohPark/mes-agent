import json
import os
from pathlib import Path

from .model import Workflow, WorkflowStep


def _workflow_dir() -> Path | None:
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault:
        return None
    return Path(vault) / "agent" / "workflows"


def load_workflow(task_type: str, thread_id: str) -> Workflow | None:
    d = _workflow_dir()
    if not d:
        return None
    path = d / task_type / f"{thread_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Workflow.from_dict(data)
    except Exception:
        return None


def save_workflow(workflow: Workflow) -> None:
    d = _workflow_dir()
    if not d:
        return
    path = d / workflow.task_type / f"{workflow.thread_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_workflow(task_type: str, thread_id: str) -> None:
    d = _workflow_dir()
    if not d:
        return
    path = d / task_type / f"{thread_id}.json"
    if path.exists():
        path.unlink()
