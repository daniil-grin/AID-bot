"""
core/utils.py — общие вспомогательные функции.

Исправления:
  - check_cooldown: используется datetime.now() однократно (не дважды)
  - ensure_panel_is_last: принимает bot явно, не достаёт его через _state
  - on_error обработчик в modal через on_error
"""
from __future__ import annotations

from datetime import datetime, timedelta

import discord

from core import config, storage


# ── Роли ─────────────────────────────────────────────────

def has_reviewer_role(member: discord.Member) -> bool:
    """Хотя бы одна роль рецензента."""
    ids = {r.id for r in member.roles}
    return bool(ids & set(config.REVIEWER_ROLE_IDS))


# ── Кулдаун ──────────────────────────────────────────────

async def check_cooldown(interaction: discord.Interaction) -> bool:
    """True — можно продолжать; False — кулдаун, ответ уже отправлен."""
    uid  = interaction.user.id
    cd   = storage.user_cooldowns
    now  = datetime.now()  # один вызов — нет расхождения по времени

    if uid in cd:
        rem = (cd[uid] - now).total_seconds()
        if rem > 0:
            await interaction.response.send_message(
                f"⏳ Следующую заявку можно отправить через **{int(rem)} сек.**",
                ephemeral=True,
            )
            return False

    cd[uid] = now + timedelta(seconds=config.COOLDOWN_SECONDS)
    return True


# ── Идентификаторы и базовые записи ──────────────────────

def make_app_id(user_id: int) -> str:
    return f"{user_id}_{int(datetime.now().timestamp())}"


def base_record(interaction: discord.Interaction, app_type: str) -> dict:
    return {
        "user_id":   interaction.user.id,
        "username":  str(interaction.user),
        "type":      app_type,
        "status":    "ожидает",
        "timestamp": datetime.now().isoformat(),
    }


# ── Валидация ────────────────────────────────────────────

def validate_static_id(value: str) -> bool:
    """Статик ID — только цифры, от 3 до 10 символов."""
    v = value.strip()
    return v.isdigit() and 3 <= len(v) <= 10


# ── Панель ───────────────────────────────────────────────

def build_panel_embed() -> discord.Embed:
    embed = discord.Embed(title="Подача заявки", color=0x2B2D31)
    embed.add_field(
        name="Выберите тип заявки:",
        value=(
            "🟢 **Академия** — зачисление в академию\n"
            "🔵 **Перевод** — из другой структуры\n"
            "⚪ **Гос. сотрудник** — для гостей"
        ),
        inline=False,
    )
    embed.set_footer(
        text=f"⏱ Новую заявку можно отправить через {config.COOLDOWN_SECONDS} сек. Хранение: 7 дней."
    )
    return embed


async def recreate_panel(bot: discord.Client, channel: discord.TextChannel) -> discord.Message:
    """Удаляет старую панель и отправляет новую последним сообщением."""
    from cogs.views import ApplicationMenuView  # локальный импорт — избегаем цикла

    old_id = storage.config.get("panel_message_id")
    if old_id:
        try:
            await (await channel.fetch_message(old_id)).delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    msg = await channel.send(embed=build_panel_embed(), view=ApplicationMenuView())
    storage.config["panel_message_id"] = msg.id
    await storage.save_config()
    return msg


async def ensure_panel_is_last(bot: discord.Client, channel: discord.TextChannel) -> None:
    """Если панель не последнее сообщение — пересоздаём её."""
    pid = storage.config.get("panel_message_id")
    if not pid:
        return
    msgs = [m async for m in channel.history(limit=1)]
    if msgs and msgs[0].id != pid:
        await recreate_panel(bot, channel)


# ── Embed заявки ─────────────────────────────────────────

async def send_application_embed(
    bot: discord.Client,
    interaction: discord.Interaction,
    app_id: str,
    fields: dict[str, tuple[str, bool]],
    app_type: str,
    color: int,
) -> None:
    """Строит embed заявки и отправляет его в канал модераторов."""
    from cogs.views import ApplicationControlView

    app = storage.applications[app_id]

    embed = discord.Embed(color=color)
    embed.set_author(name=app_type, icon_url=interaction.user.display_avatar.url)
    for name, (value, inline) in fields.items():
        embed.add_field(name=name, value=value, inline=inline)
    embed.add_field(name="Статус", value="⏳ ожидает", inline=False)
    embed.set_footer(
        text=f"{app_type} | {app['first_name']} {app['last_name']} "
             f"• Сегодня, в {datetime.now().strftime('%H:%M')}",
        icon_url=interaction.user.display_avatar.url,
    )

    ch = bot.get_channel(config.APPLICATIONS_CHANNEL_ID)
    if ch:
        msg = await ch.send(embed=embed, view=ApplicationControlView(app_id=app_id))
        storage.applications[app_id]["message_id"] = msg.id
        storage.applications[app_id]["channel_id"] = ch.id
        await storage.save_applications()

    panel_ch = bot.get_channel(config.PANEL_CHANNEL_ID)
    if panel_ch:
        await ensure_panel_is_last(bot, panel_ch)
