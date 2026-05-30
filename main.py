"""
main.py — точка входа. Запуск: python main.py
"""
import asyncio
import logging
import sys
import subprocess

import discord
from discord.ext import commands

from core.config import BOT_TOKEN

subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--no-index"], capture_output=True)

# ── Логирование ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("bot")


async def main():
    intents = discord.Intents.default()
    intents.members = True  # нужен для get_member() и смены ника
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    await bot.load_extension("cogs.commands")
    await bot.load_extension("cogs.tasks")

    @bot.event
    async def on_ready():
        log.info(f"Бот запущен: {bot.user} ({bot.user.id})")
        try:
            synced = await bot.tree.sync()
            log.info(f"Синхронизировано {len(synced)} команд")
        except Exception as e:
            log.error(f"Ошибка синхронизации команд: {e}")

    @bot.event
    async def on_error(event: str, *args, **kwargs):
        log.exception(f"Необработанная ошибка в событии {event!r}")

    try:
        await bot.start(BOT_TOKEN)
    except discord.LoginFailure:
        log.critical("Неверный токен бота (BOT_TOKEN). Проверьте .env")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
