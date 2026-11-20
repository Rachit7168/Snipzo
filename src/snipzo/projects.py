"""Load and resolve Snipzo projects from a work directory."""

from __future__ import annotations

from pathlib import Path

from snipzo.errors import SnipzoError
from snipzo.models import Project
from snipzo.storage import LocalStorage, Storage


def get_storage(work_dir: Path) -> LocalStorage:
    """Return local disk storage under `work_dir`."""
    return LocalStorage(work_dir)


def resolve_project(ref: str, storage: Storage) -> Project:
    """Load a project by ID or by path to its directory / project.json."""
    path = Path(ref).expanduser()
    json_path: Path | None = None
    if path.is_file() and path.name == "project.json":
        json_path = path
    elif path.is_dir() and (path / "project.json").is_file():
        json_path = path / "project.json"
    if json_path is not None:
        try:
            return Project.model_validate_json(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SnipzoError(f"Could not load project {ref}: {exc}") from exc
    if not storage.exists(ref, "project.json"):
        raise SnipzoError(f"Project not found: {ref}")
    try:
        return storage.load_project(ref)
    except (OSError, ValueError) as exc:
        raise SnipzoError(f"Could not load project {ref}: {exc}") from exc
