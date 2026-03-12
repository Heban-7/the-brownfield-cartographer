"""Git-based change velocity analysis using GitPython."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError

logger = logging.getLogger(__name__)


def _open_repo(repo_path: str | Path) -> Optional[Repo]:
    try:
        return Repo(str(repo_path), search_parent_directories=True)
    except InvalidGitRepositoryError:
        logger.warning("Not a git repository: %s", repo_path)
        return None
    except Exception as exc:
        logger.warning("Cannot open git repo at %s: %s", repo_path, exc)
        return None


def extract_git_velocity(
    repo_path: str | Path, days: int = 30
) -> dict[str, int]:
    """Return a mapping of relative file path -> commit count in the last *days* days."""
    repo = _open_repo(repo_path)
    if repo is None:
        return {}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    counter: Counter[str] = Counter()

    try:
        for commit in repo.iter_commits(since=since.isoformat()):
            for path in commit.stats.files:
                counter[path] += 1
    except Exception as exc:
        logger.warning("Error reading git log: %s", exc)

    return dict(counter)


def get_high_velocity_files(
    repo_path: str | Path, days: int = 30, top_pct: float = 0.2
) -> list[tuple[str, int]]:
    """Return the top *top_pct* fraction of files by change frequency."""
    velocity = extract_git_velocity(repo_path, days)
    if not velocity:
        return []
    sorted_files = sorted(velocity.items(), key=lambda x: x[1], reverse=True)
    cutoff = max(1, int(len(sorted_files) * top_pct))
    return sorted_files[:cutoff]


def get_recent_commits(
    repo_path: str | Path, count: int = 20
) -> list[dict]:
    """Return metadata for the *count* most recent commits."""
    repo = _open_repo(repo_path)
    if repo is None:
        return []

    commits = []
    try:
        for commit in repo.iter_commits(max_count=count):
            commits.append({
                "sha": commit.hexsha[:8],
                "message": commit.message.strip().split("\n")[0],
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
                "files_changed": list(commit.stats.files.keys()),
            })
    except Exception as exc:
        logger.warning("Error reading recent commits: %s", exc)

    return commits


def get_changed_files_since(
    repo_path: str | Path, since_timestamp: datetime
) -> list[str]:
    """Return files changed since a given timestamp (for incremental updates)."""
    repo = _open_repo(repo_path)
    if repo is None:
        return []

    changed: set[str] = set()
    try:
        for commit in repo.iter_commits(since=since_timestamp.isoformat()):
            changed.update(commit.stats.files.keys())
    except Exception as exc:
        logger.warning("Error reading changed files: %s", exc)

    return sorted(changed)
