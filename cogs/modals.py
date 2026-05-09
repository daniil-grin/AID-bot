"""
cogs/modals.py — модальные формы подачи и редактирования заявок.

Исправления:
  - on_error перехватывает необработанные исключения в каждой форме
  - save_applications теперь awaitable (async)
  - .strip() на всех полях перенесён в единую точку при сборке record
"""
from __future__ import annotations

import logging

import discord

from core import storage
from core.utils import check_cooldown, make_app_id, base_record, send_application_embed, validate_static_id


log = logging.getLogger(__name__)


async def _on_modal_error(interaction: discord.Interaction, error: Exception) -> None:
    """Общий обработчик ошибок для всех модалок."""
    log.error(f"[modal error] {type(error).__name__}: {error}")
    msg = "❌ Произошла внутренняя ошибка. Попробуйте позже."
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)


# ── Академия ──────────────────────────────────────────────

class AcademyModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Заявка на получение роли")
        self.first_name = discord.ui.TextInput(
            label="Имя", placeholder="Введите ваше имя", required=True, max_length=50)
        self.last_name = discord.ui.TextInput(
            label="Фамилия", placeholder="Введите вашу фамилию", required=True, max_length=50)
        self.static_id = discord.ui.TextInput(
            label="Статик ID", placeholder="Введите цифры (пример: 588167)",
            required=True, min_length=3, max_length=10)
        self.reason = discord.ui.TextInput(
            label="Причина", placeholder="Электронная заявка / собеседование",
            required=True, max_length=300, style=discord.TextStyle.paragraph)
        for item in (self.first_name, self.last_name, self.static_id, self.reason):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not validate_static_id(self.static_id.value):
            await interaction.response.send_message(
                "❌ Статик ID должен содержать только цифры (3–10 символов).", ephemeral=True)
            return
        if not await check_cooldown(interaction):
            return

        app_id = make_app_id(interaction.user.id)
        record = base_record(interaction, "Академия")
        record.update({
            "first_name": self.first_name.value.strip(),
            "last_name":  self.last_name.value.strip(),
            "static_id":  self.static_id.value.strip(),
            "reason":     self.reason.value.strip(),
        })
        storage.applications[app_id] = record
        await storage.save_applications()

        await send_application_embed(
            interaction.client, interaction, app_id,
            fields={
                "Имя":       (record["first_name"], True),
                "Фамилия":   (record["last_name"],  True),
                "Статик ID": (record["static_id"],  True),
                "Причина":   (record["reason"],      False),
            },
            app_type="Академия", color=0x57F287,
        )
        await interaction.response.send_message(
            "✅ Ваша заявка **(Академия)** отправлена! Ожидайте рассмотрения.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await _on_modal_error(interaction, error)


# ── Перевод / Восстановление ─────────────────────────────

class TransferModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Заявка на перевод")
        self.first_name = discord.ui.TextInput(
            label="Имя", placeholder="Введите ваше имя", required=True, max_length=50)
        self.last_name = discord.ui.TextInput(
            label="Фамилия", placeholder="Введите вашу фамилию", required=True, max_length=50)
        self.static_id = discord.ui.TextInput(
            label="Статик ID", placeholder="Введите цифры (пример: 588167)",
            required=True, min_length=3, max_length=10)
        self.rank = discord.ui.TextInput(
            label="Звание", placeholder="Введите ваше текущее звание",
            required=True, max_length=80)
        self.approval = discord.ui.TextInput(
            label="Одобрение", placeholder="Ссылка на одобрение / подтверждение",
            required=True, max_length=500, style=discord.TextStyle.paragraph)
        for item in (self.first_name, self.last_name, self.static_id, self.rank, self.approval):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not validate_static_id(self.static_id.value):
            await interaction.response.send_message(
                "❌ Статик ID должен содержать только цифры (3–10 символов).", ephemeral=True)
            return
        if not await check_cooldown(interaction):
            return

        app_id = make_app_id(interaction.user.id)
        record = base_record(interaction, "Перевод")
        record.update({
            "first_name": self.first_name.value.strip(),
            "last_name":  self.last_name.value.strip(),
            "static_id":  self.static_id.value.strip(),
            "rank":       self.rank.value.strip(),
            "approval":   self.approval.value.strip(),
        })
        storage.applications[app_id] = record
        await storage.save_applications()

        await send_application_embed(
            interaction.client, interaction, app_id,
            fields={
                "Имя":       (record["first_name"], True),
                "Фамилия":   (record["last_name"],  True),
                "Статик ID": (record["static_id"],  True),
                "Звание":    (record["rank"],        False),
                "Одобрение": (record["approval"],    False),
            },
            app_type="Перевод", color=0x5865F2,
        )
        await interaction.response.send_message(
            "✅ Ваша заявка **(Перевод)** отправлена! Ожидайте рассмотрения.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await _on_modal_error(interaction, error)


# ── Гос. Сотрудник ───────────────────────────────────────

class GovModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Заявка для гос сотрудников")
        self.first_name = discord.ui.TextInput(
            label="Имя", placeholder="Введите ваше имя", required=True, max_length=50)
        self.last_name = discord.ui.TextInput(
            label="Фамилия", placeholder="Введите вашу фамилию", required=True, max_length=50)
        self.static_id = discord.ui.TextInput(
            label="Статик ID", placeholder="Введите цифры (пример: 588167)",
            required=True, min_length=3, max_length=10)
        self.approval = discord.ui.TextInput(
            label="Одобрение", placeholder="Ссылка на одобрение / подтверждение",
            required=True, max_length=500, style=discord.TextStyle.paragraph)
        for item in (self.first_name, self.last_name, self.static_id, self.approval):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not validate_static_id(self.static_id.value):
            await interaction.response.send_message(
                "❌ Статик ID должен содержать только цифры (3–10 символов).", ephemeral=True)
            return
        if not await check_cooldown(interaction):
            return

        app_id = make_app_id(interaction.user.id)
        record = base_record(interaction, "Гос. Сотрудник")
        record.update({
            "first_name": self.first_name.value.strip(),
            "last_name":  self.last_name.value.strip(),
            "static_id":  self.static_id.value.strip(),
            "approval":   self.approval.value.strip(),
        })
        storage.applications[app_id] = record
        await storage.save_applications()

        await send_application_embed(
            interaction.client, interaction, app_id,
            fields={
                "Имя":       (record["first_name"], True),
                "Фамилия":   (record["last_name"],  True),
                "Статик ID": (record["static_id"],  True),
                "Одобрение": (record["approval"],    False),
            },
            app_type="Гос. Сотрудник", color=0x99AAB5,
        )
        await interaction.response.send_message(
            "✅ Ваша заявка **(Гос. Сотрудник)** отправлена! Ожидайте рассмотрения.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await _on_modal_error(interaction, error)


# ── Редактирование ───────────────────────────────────────

class EditApplicationModal(discord.ui.Modal):
    def __init__(self, app_id: str):
        super().__init__(title="Редактировать заявку")
        self.app_id  = app_id
        app          = storage.applications.get(app_id, {})
        app_type     = app.get("type", "")

        self.first_name = discord.ui.TextInput(
            label="Имя", default=app.get("first_name", ""), required=True, max_length=50)
        self.last_name = discord.ui.TextInput(
            label="Фамилия", default=app.get("last_name", ""), required=True, max_length=50)
        self.static_id = discord.ui.TextInput(
            label="Статик ID", default=app.get("static_id", ""), required=True, max_length=10)

        if app_type == "Перевод":
            self.extra = discord.ui.TextInput(
                label="Звание", default=app.get("rank", ""), required=False, max_length=80)
        elif app_type == "Гос. Сотрудник":
            self.extra = discord.ui.TextInput(
                label="Одобрение", default=app.get("approval", ""),
                required=False, max_length=500, style=discord.TextStyle.paragraph)
        else:
            self.extra = discord.ui.TextInput(
                label="Причина", default=app.get("reason", ""),
                required=False, max_length=300, style=discord.TextStyle.paragraph)

        for item in (self.first_name, self.last_name, self.static_id, self.extra):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not validate_static_id(self.static_id.value):
            await interaction.response.send_message(
                "❌ Статик ID должен содержать только цифры (3–10 символов).", ephemeral=True)
            return

        app = storage.applications.get(self.app_id)
        if not app:
            await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
            return

        # Нельзя редактировать уже обработанную заявку
        if app["status"] != "ожидает":
            await interaction.response.send_message(
                f"⚠️ Нельзя редактировать заявку со статусом «{app['status']}».", ephemeral=True)
            return

        app_type = app.get("type", "")
        update = {
            "first_name": self.first_name.value.strip(),
            "last_name":  self.last_name.value.strip(),
            "static_id":  self.static_id.value.strip(),
        }
        if app_type == "Перевод":
            update["rank"] = self.extra.value.strip()
        elif app_type == "Гос. Сотрудник":
            update["approval"] = self.extra.value.strip()
        else:
            update["reason"] = self.extra.value.strip()

        storage.applications[self.app_id].update(update)
        await storage.save_applications()

        # Обновить embed в канале заявок
        try:
            ch = interaction.client.get_channel(app.get("channel_id"))
            if ch:
                msg     = await ch.fetch_message(app["message_id"])
                old     = msg.embeds[0]
                mapping = {
                    "Перевод":        {"Звание":    update.get("rank", "")},
                    "Гос. Сотрудник": {"Одобрение": update.get("approval", "")},
                }.get(app_type, {"Причина": update.get("reason", "")})
                mapping.update({
                    "Имя":       update["first_name"],
                    "Фамилия":   update["last_name"],
                    "Статик ID": update["static_id"],
                })
                new_embed = discord.Embed(color=old.color)
                new_embed.set_author(name=old.author.name, icon_url=old.author.icon_url)
                for f in old.fields:
                    new_embed.add_field(
                        name=f.name, value=mapping.get(f.name, f.value), inline=f.inline)
                new_embed.set_footer(text=old.footer.text, icon_url=old.footer.icon_url)
                await msg.edit(embed=new_embed)
        except discord.NotFound:
            log.warning(f"[EditModal] Сообщение заявки {self.app_id} не найдено")
        except Exception as e:
            log.error(f"[EditModal] Ошибка обновления embed: {e}")

        await interaction.response.send_message("✅ Заявка обновлена.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await _on_modal_error(interaction, error)
