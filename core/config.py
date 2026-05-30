"""
core/config.py — загрузка переменных окружения из .env
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise ValueError(f"[config] Обязательная переменная {key!r} не задана в .env")
    return val


def _int(key: str) -> int:
    raw = _require(key)
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"[config] {key!r} должна быть целым числом, получено: {raw!r}")


def _int_list(key: str, required: bool = False) -> list[int]:
    raw = os.getenv(key, "").strip()
    if not raw:
        if required:
            raise ValueError(f"[config] {key!r} не задана — укажите хотя бы один ID")
        return []
    result = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            raise ValueError(f"[config] {key!r}: {part!r} не является целым числом")
    return result


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("true", "1", "yes")


# ── Основные ──────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")

# ── Каналы ────────────────────────────────────────────────
PANEL_CHANNEL_ID:        int = _int("PANEL_CHANNEL_ID")
APPLICATIONS_CHANNEL_ID: int = _int("APPLICATIONS_CHANNEL_ID")
AUDIT_CHANNEL_ID:        int = _int("AUDIT_CHANNEL_ID")

# ── Поведение ─────────────────────────────────────────────
COOLDOWN_SECONDS:        int = int(os.getenv("COOLDOWN_SECONDS", "60"))
CHANGE_NICKNAME:         bool = _bool("CHANGE_NICKNAME", True)

NICKNAME_FORMATS: dict[str, str] = {
    "Академия":       os.getenv("NICKNAME_FORMAT_ACADEMY",  "Академия | {first_name} {last_name}"),
    "Перевод":        os.getenv("NICKNAME_FORMAT_TRANSFER", "{first_name} {last_name} | {static_id}"),
    "Гос. Сотрудник": os.getenv("NICKNAME_FORMAT_GOV",      "{first_name} {last_name} | {static_id}"),
}

# Проверяем что каждый формат содержит {first_name}
if CHANGE_NICKNAME:
    for _app_type, _fmt in NICKNAME_FORMATS.items():
        if "{first_name}" not in _fmt:
            raise ValueError(
                f"[config] NICKNAME_FORMAT для '{_app_type}' должен содержать {{first_name}}, "
                f"получено: {_fmt!r}"
            )

# ── Роли ──────────────────────────────────────────────────
REVIEWER_ROLE_IDS: list[int] = _int_list("REVIEWER_ROLE_IDS", required=True)

GRANT_ROLE_IDS: dict[str, list[int]] = {
    "Академия":        _int_list("GRANT_ROLES_ACADEMY"),
    "Перевод":        _int_list("GRANT_ROLES_TRANSFER"),
    "Гос. Сотрудник": _int_list("GRANT_ROLES_GOV"),
}
