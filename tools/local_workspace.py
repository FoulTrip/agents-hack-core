from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any

from core.config import settings
from core.logger import get_logger
from tools.file_map import flatten_files_payload

logger = get_logger(__name__)


def _is_local_generation_enabled() -> bool:
    return bool(getattr(settings, "LOCAL_GENERATION_ENABLED", True))


def _sanitize_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", value or "")
    safe = safe.strip("-._")
    return safe or "unknown"


def _normalize_repo_full_name(repo_full_name: str) -> str:
    raw = (repo_full_name or "").strip()
    if not raw:
        return ""

    raw = raw.replace("https://github.com/", "").replace("http://github.com/", "")
    raw = raw.strip().strip("/")

    if raw.lower().endswith(".git"):
        raw = raw[:-4]

    return raw


def _split_repo(repo_full_name: str) -> tuple[str, str]:
    normalized = _normalize_repo_full_name(repo_full_name)
    if not normalized or "/" not in normalized:
        return "unknown", _sanitize_segment(normalized or "project")
    owner, repo = normalized.split("/", 1)
    return _sanitize_segment(owner), _sanitize_segment(repo)


def get_project_local_path(repo_full_name: str) -> str:
    owner, repo = _split_repo(repo_full_name)
    base = Path(getattr(settings, "LOCAL_PROJECTS_DIR", "./generated_projects")).resolve()
    return str((base / f"{owner}__{repo}").resolve())


def _safe_relative_path(path: str) -> str | None:
    normalized = (path or "").replace("\\", "/").strip()
    # Algunos outputs de agentes llegan con comillas envolventes:
    # e.g. "\"backend/Dockerfile\"" o "'docs/README.md'".
    normalized = normalized.strip("\"'").lstrip("/")
    if not normalized:
        return None
    raw_parts = [p for p in normalized.split("/") if p not in ("", ".")]
    safe_parts: list[str] = []
    for part in raw_parts:
        cleaned = (part or "").strip().strip("\"'")
        if not cleaned:
            continue
        if cleaned == "..":
            return None
        # Evita caracteres inválidos para rutas en Windows.
        cleaned = re.sub(r'[<>:"|?*]', "-", cleaned)
        cleaned = cleaned.rstrip(" .")
        if cleaned:
            safe_parts.append(cleaned)
    if not safe_parts:
        return None
    return "/".join(safe_parts)


def sync_project_files_local(repo_full_name: str, files: dict) -> Dict[str, Any]:
    """Escribe archivos del proyecto en disco local y devuelve un resumen."""
    if not _is_local_generation_enabled():
        return {
            "enabled": False,
            "local_project_path": None,
            "written_count": 0,
            "written_files": [],
            "errors": [],
        }

    local_project_path = Path(get_project_local_path(repo_full_name))
    local_project_path.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    errors: list[str] = []

    if not isinstance(files, dict):
        return {
            "enabled": True,
            "local_project_path": str(local_project_path),
            "written_count": 0,
            "written_files": [],
            "errors": ["'files' no es un diccionario válido"],
        }

    normalized_files = flatten_files_payload(files)
    if not normalized_files and files:
        errors.append("No se encontraron archivos válidos para escribir (payload anidado o vacío).")

    for raw_path, raw_content in normalized_files.items():
        safe_rel = _safe_relative_path(str(raw_path))
        if not safe_rel:
            errors.append(f"Ruta inválida omitida: {raw_path}")
            continue

        target = (local_project_path / safe_rel).resolve()
        if local_project_path not in target.parents and target != local_project_path:
            errors.append(f"Ruta fuera de workspace omitida: {raw_path}")
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            content = raw_content if isinstance(raw_content, str) else str(raw_content)
            target.write_text(content, encoding="utf-8")
            written_files.append(safe_rel)
        except Exception as e:
            errors.append(f"{safe_rel}: {e}")

    logger.info(
        f"Workspace local sincronizado para {repo_full_name}: escritos={len(written_files)} errores={len(errors)} ruta={local_project_path}"
    )
    if errors:
        logger.warning(f"Errores al sincronizar workspace local ({repo_full_name}): {errors[:5]}")

    return {
        "enabled": True,
        "local_project_path": str(local_project_path),
        "written_count": len(written_files),
        "written_files": written_files,
        "errors": errors,
    }
