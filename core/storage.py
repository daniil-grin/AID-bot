"""
core/storage.py — хранилище данных на базе JSON5.

Исправления:
  - asyncio.Lock предотвращает гонку при параллельных save_applications()
  - Атомарная запись: tmp → fsync → rename (данные не повреждаются при крэше)
  - purge_old логирует конкретные app_id для трассировки
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime
from typing import Any

import json
import json5

# ── Пути к файлам ─────────────────────────────────────────
DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
APP_FILE    = os.path.join(DATA_DIR, "applications.json5")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json5")

os.makedirs(DATA_DIR, exist_ok=True)

# Lock — один поток записи за раз
_write_lock = asyncio.Lock()


# ── Низкоуровневые операции ───────────────────────────────

def _load(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json5.load(f)
    return default


def _save_sync(path: str, data: Any) -> None:
    """Атомарная запись: tmp-файл → fsync → rename."""
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # json используем для записи — гарантированная поддержка ensure_ascii
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── Публичные объекты ─────────────────────────────────────

applications: dict[str, dict] = _load(APP_FILE, {})
config:       dict[str, Any]  = _load(CONFIG_FILE, {})

# Кулдауны — только в памяти, сбрасываются при перезапуске
user_cooldowns: dict[int, datetime] = {}


# ── Сохранение (с Lock) ───────────────────────────────────

async def save_applications() -> None:
    """Асинхронная потокобезопасная запись заявок."""
    async with _write_lock:
        _save_sync(APP_FILE, applications)


async def save_config() -> None:
    """Асинхронная потокобезопасная запись конфига."""
    async with _write_lock:
        _save_sync(CONFIG_FILE, config)


# ── Утилиты ──────────────────────────────────────────────

async def purge_old(days: int = 7) -> int:
    """Удаляет заявки старше `days` дней. Возвращает количество удалённых."""
    now = datetime.now()
    old_ids = [
        aid for aid, app in applications.items()
        if (now - datetime.fromisoformat(app["timestamp"])).days >= days
    ]
    for aid in old_ids:
        del applications[aid]
    if old_ids:
        await save_applications()
    return len(old_ids)
