"""
cogs/tasks.py — фоновые задачи.
"""
from __future__ import annotations

import logging

from discord.ext import commands, tasks

from core import config, storage
from core.utils import ensure_panel_is_last

log = logging.getLogger(__name__)


class BackgroundTasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_watchdog.start()
        self.cleanup_old.start()

    def cog_unload(self):
        self.panel_watchdog.cancel()
        self.cleanup_old.cancel()

    @tasks.loop(seconds=30)
    async def panel_watchdog(self):
        """Каждые 30 сек убеждается, что панель — последнее сообщение в канале."""
        try:
            ch = self.bot.get_channel(config.PANEL_CHANNEL_ID)
            if ch and storage.config.get("panel_message_id"):
                await ensure_panel_is_last(self.bot, ch)
        except Exception as e:
            log.warning(f"[watchdog] {e}")

    @panel_watchdog.before_loop
    async def before_watchdog(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def cleanup_old(self):
        """Каждый час удаляет заявки старше 7 дней."""
        removed = await storage.purge_old(days=7)
        if removed:
            log.info(f"Удалено старых заявок: {removed}")

    @cleanup_old.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(BackgroundTasks(bot))
