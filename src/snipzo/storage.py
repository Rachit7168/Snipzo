"""Storage abstraction. Local disk now; S3/R2 can implement the same protocol later."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from snipzo.models import Project


@runtime_checkable
class Storage(Protocol):
    """Read and write project files."""

    def project_root(self, project_id: str) -> Path:
        """Return the directory for a project, creating it if needed."""
        ...

    def copy_into(self, project_id: str, src: Path, dest_name: str) -> Path:
        """Copy a file into the project directory and return the destination."""
        ...

    def write_bytes(self, project_id: str, dest_name: str, data: bytes) -> Path:
        """Write raw bytes into the project directory."""
        ...

    def write_json(self, project_id: str, dest_name: str, payload: object) -> Path:
        """Serialize `payload` as JSON in the project directory."""
        ...

    def read_json(self, project_id: str, dest_name: str) -> object:
        """Load a JSON file from the project directory."""
        ...

    def exists(self, project_id: str, dest_name: str) -> bool:
        """Return whether a named file exists in the project directory."""
        ...

    def save_project(self, project: Project) -> Path:
        """Persist `project.json` for a project."""
        ...

    def load_project(self, project_id: str) -> Project:
        """Load a project from `project.json`."""
        ...


class LocalStorage:
    """Filesystem storage under a working directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def project_root(self, project_id: str) -> Path:
        path = self.root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _path(self, project_id: str, dest_name: str) -> Path:
        path = self.project_root(project_id) / dest_name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def copy_into(self, project_id: str, src: Path, dest_name: str) -> Path:
        dest = self._path(project_id, dest_name)
        shutil.copy2(src, dest)
        return dest

    def write_bytes(self, project_id: str, dest_name: str, data: bytes) -> Path:
        dest = self._path(project_id, dest_name)
        dest.write_bytes(data)
        return dest

    def write_json(self, project_id: str, dest_name: str, payload: object) -> Path:
        dest = self._path(project_id, dest_name)
        dest.write_text(
            json.dumps(payload, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )
        return dest

    def read_json(self, project_id: str, dest_name: str) -> object:
        path = self._path(project_id, dest_name)
        return json.loads(path.read_text(encoding="utf-8"))

    def exists(self, project_id: str, dest_name: str) -> bool:
        return (self.root / project_id / dest_name).is_file()

    def save_project(self, project: Project) -> Path:
        """Persist `project.json` for a project."""
        return self.write_json(
            project.id, "project.json", project.model_dump(mode="json")
        )

    def load_project(self, project_id: str) -> Project:
        """Load a project from `project.json`."""
        payload = self.read_json(project_id, "project.json")
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid project.json for {project_id}")
        return Project.model_validate(payload)


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
