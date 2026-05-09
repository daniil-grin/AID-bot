"""
cogs/commands.py — слэш-команды бота (Cog).
"""
from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

from core import config, storage
from core.utils import recreate_panel
from cogs.views import ApplicationMenuView, ApplicationControlView


class ApplicationCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_applications", description="Создать / пересоздать панель заявок")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_applications(self, interaction: discord.Interaction):
        ch = self.bot.get_channel(config.PANEL_CHANNEL_ID)
        if not ch:
            await interaction.response.send_message("❌ PANEL_CHANNEL_ID не найден.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await recreate_panel(self.bot, ch)
        await interaction.followup.send("✅ Панель пересоздана!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplicationCommands(bot))

    # Восстанавливаем постоянные View после перезапуска
    bot.add_view(ApplicationMenuView())
    for app_id, app in storage.applications.items():
        if app.get("status") == "ожидает":
            bot.add_view(ApplicationControlView(app_id=app_id))
