"""
cogs/views.py — постоянные View: панель заявок и кнопки управления.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import discord

from core import config, storage
from core.utils import has_reviewer_role
from cogs.modals import AcademyModal, TransferModal, GovModal, EditApplicationModal

log = logging.getLogger(__name__)

# Хранилище фоновых задач — предотвращает преждевременную сборку GC
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ── Вспомогательные функции ──────────────────────────────

async def _grant_roles_batch(member: discord.Member, roles: list[discord.Role], reason: str) -> str:
    if not roles:
        return ""
    try:
        await member.add_roles(*roles, reason=reason)
        return "🎖 Выданы роли: " + ", ".join(f"**{r.name}**" for r in roles)
    except discord.Forbidden:
        return "⚠️ Нет прав выдать роли (проверьте иерархию)"
    except Exception as e:
        return f"⚠️ Ошибка ролей: {e}"


async def _change_nick(member: discord.Member, new_nick: str) -> str:
    try:
        await member.edit(nick=new_nick, reason="Заявка принята")
        return f"✏️ Ник → **{new_nick}**"
    except discord.Forbidden:
        return "⚠️ Нет прав сменить ник"
    except Exception as e:
        return f"⚠️ Ошибка ника: {e}"


async def _send_audit(client: discord.Client, app: dict, reviewer_mention: str, jump_url: str) -> None:
    if app["type"] not in ("Академия", "Перевод"):
        return
    audit_ch = client.get_channel(config.AUDIT_CHANNEL_ID)
    if not audit_ch:
        return
    try:
        accepted_user = await client.fetch_user(app["user_id"])
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        await audit_ch.send(
            f"1. {reviewer_mention}\n"
            f"2. {accepted_user.mention}\n"
            f"3. Принят согласно: {jump_url}\n"
            f"4. {now_str}"
        )
    except Exception as e:
        log.warning(f"[audit] {e}")


async def _send_dm(
    client: discord.Client,
    app: dict,
    status: str,
    color: int,
    reviewer: str,
    new_nick: str | None,
) -> None:
    try:
        target = await client.fetch_user(app["user_id"])
        dm = discord.Embed(
            title="📋 Статус вашей заявки обновлён",
            description=f"Заявка типа **{app['type']}** была **{status}**.",
            color=color,
        )
        dm.add_field(name="Проверил", value=reviewer, inline=True)
        if new_nick:
            dm.add_field(name="Ваш новый ник", value=new_nick, inline=True)
        await target.send(embed=dm)
    except Exception:
        pass  # Пользователь закрыл DM — не критично


# ── Главное меню ─────────────────────────────────────────

class ApplicationMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Академия", style=discord.ButtonStyle.success,
                       emoji="🟢", custom_id="menu_academy")
    async def academy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open(interaction, AcademyModal())

    @discord.ui.button(label="Перевод / Восстановление", style=discord.ButtonStyle.primary,
                       emoji="🔵", custom_id="menu_transfer")
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open(interaction, TransferModal())

    @discord.ui.button(label="Гос. Сотрудник", style=discord.ButtonStyle.secondary,
                       emoji="⚪", custom_id="menu_gov")
    async def gov(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open(interaction, GovModal())

    async def _open(self, interaction: discord.Interaction, modal: discord.ui.Modal):
        uid = interaction.user.id
        cd  = storage.user_cooldowns
        now = datetime.now()
        if uid in cd:
            rem = (cd[uid] - now).total_seconds()
            if rem > 0:
                await interaction.response.send_message(
                    f"⏳ Новую заявку можно отправить через **{int(rem)} сек.**",
                    ephemeral=True,
                )
                return
        await interaction.response.send_modal(modal)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        log.error(f"[MenuView error] {type(error).__name__}: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


# ── Кнопки управления заявкой ────────────────────────────

class ApplicationControlView(discord.ui.View):
    def __init__(self, app_id: str):
        super().__init__(timeout=None)
        self.app_id = app_id

    @discord.ui.button(label="Принять",       style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="ctrl_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process(interaction, accepted=True)

    @discord.ui.button(label="Отклонить",     style=discord.ButtonStyle.danger,
                       emoji="✖",  custom_id="ctrl_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process(interaction, accepted=False)

    @discord.ui.button(label="Редактировать", style=discord.ButtonStyle.secondary,
                       emoji="✏️", custom_id="ctrl_edit")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_reviewer_role(interaction.user):
            await interaction.response.send_message(
                "🚫 У вас нет прав для редактирования.", ephemeral=True)
            return
        app = storage.applications.get(self.app_id)
        if not app:
            await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
            return
        await interaction.response.send_modal(EditApplicationModal(self.app_id))

    async def _process(self, interaction: discord.Interaction, accepted: bool):
        if not has_reviewer_role(interaction.user):
            await interaction.response.send_message(
                "🚫 У вас нет прав для рассмотрения заявок.", ephemeral=True)
            return

        app = storage.applications.get(self.app_id)
        if not app:
            await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
            return

        # Оптимистичная блокировка: меняем статус в памяти ДО первого await
        # — двойное нажатие от двух модераторов одновременно не пройдёт
        if app["status"] != "ожидает":
            await interaction.response.send_message(
                f"⚠️ Заявка уже обработана: «{app['status']}»", ephemeral=True)
            return
        app["status"] = "processing"  # временная метка, пока идёт обработка

        status = "принята"  if accepted else "отклонена"
        color  = 0x57F287   if accepted else 0xED4245
        emoji  = "✅"        if accepted else "❌"

        storage.applications[self.app_id]["status"]      = status
        storage.applications[self.app_id]["reviewed_by"] = str(interaction.user)
        await storage.save_applications()

        # Обновить embed и убрать кнопки
        old       = interaction.message.embeds[0]
        new_embed = discord.Embed(color=color)
        new_embed.set_author(name=old.author.name, icon_url=old.author.icon_url)
        for f in old.fields:
            if f.name == "Статус":
                new_embed.add_field(name="Статус",    value=f"{emoji} {status}",       inline=True)
                new_embed.add_field(name="Сотрудник", value=interaction.user.mention,   inline=True)
            else:
                new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
        new_embed.set_footer(text=old.footer.text or "", icon_url=old.footer.icon_url)
        await interaction.message.edit(embed=new_embed, view=None)

        result_lines = [f"{emoji} Заявка **{status}**."]

        if accepted:
            guild  = interaction.guild
            member = guild.get_member(app["user_id"]) if guild else None

            if member:
                role_ids = config.GRANT_ROLE_IDS.get(app["type"], [])
                if not role_ids:
                    result_lines.append(f"⚠️ Роли для «{app['type']}» не заданы — роли не выданы")
                    roles_ok, roles_miss = [], []
                else:
                    roles_ok   = [r for rid in role_ids if (r := guild.get_role(rid))]
                    roles_miss = [rid for rid in role_ids if not guild.get_role(rid)]

                _fmt = config.NICKNAME_FORMATS.get(app["type"], "{first_name} {last_name}")
                new_nick = _fmt.format(
                    first_name=app["first_name"],
                    last_name=app["last_name"],
                    static_id=app["static_id"],
                    type=app["type"],
                ) if config.CHANGE_NICKNAME else None

                # Параллельно: batch-роли + ник + аудит + DM
                coros = [
                    _grant_roles_batch(member, roles_ok, f"Заявка принята: {app['type']}"),
                    _send_audit(interaction.client, app, interaction.user.mention, interaction.message.jump_url),
                    _send_dm(interaction.client, app, status, color, str(interaction.user), new_nick),
                ]
                if new_nick:
                    coros.insert(1, _change_nick(member, new_nick))

                results = await asyncio.gather(*coros)
                roles_msg = results[0]
                nick_msg  = results[1] if new_nick else ""

                if roles_miss:
                    result_lines.append("⚠️ Роли не найдены: " + ", ".join(f"`{rid}`" for rid in roles_miss))
                if roles_msg:
                    result_lines.append(roles_msg)
                if nick_msg:
                    result_lines.append(nick_msg)
            else:
                result_lines.append("⚠️ Участник не найден на сервере")

        else:
            # Отклонение: DM в фоне
            _fire_and_forget(
                _send_dm(interaction.client, app, status, color, str(interaction.user), None)
            )

        await interaction.response.send_message("\n".join(result_lines), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        log.error(f"[ControlView error] {type(error).__name__}: {error}")
        # Если статус застрял в "processing" — откатываем
        app = storage.applications.get(self.app_id)
        if app and app.get("status") == "processing":
            app["status"] = "ожидает"
            await storage.save_applications()
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Внутренняя ошибка при обработке заявки.", ephemeral=True)
