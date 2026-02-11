"""
File system utilities for the pipeline.
"""

import hashlib
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, max_length: int = 120) -> str:
    """
    Convert arbitrary string to a safe filename.
    Strips special chars, collapses whitespace, truncates.
    """
    # Remove/replace problematic characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = re.sub(r'_+', '_', name)
    name = name.strip('_.')

    if len(name) > max_length:
        name = name[:max_length].rstrip('_')
    return name or "unnamed"


def compute_content_hash(content: str) -> str:
    """SHA-256 hash of text content for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_file_hash(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(data: Any, path: Path, indent: int = 2) -> None:
    """Save data to JSON file with atomic write."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    tmp.replace(path)


def load_json(path: Path) -> Any:
    """Load JSON file, return None if missing."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def file_age_days(path: Path) -> Optional[float]:
    """Return file age in days, or None if missing."""
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds() / 86400


def write_text(text: str, path: Path) -> None:
    """Write text to file, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_text(path: Path) -> Optional[str]:
    """Read text file, return None if missing."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
