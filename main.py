"""
main.py
GMC8 — Граф Монте-Крісто AI Agent
Entry point: initializes all components, starts background tasks, runs Telegram bot.
"""
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from agent import CountAgent
from bot import GMC8Bot
from scanners import CryptoScanner, FreelanceScanner, MarketPulseScanner

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        log.error(f"Missing required env var: {name}")
        sys.exit(1)
    return val


async def main():
    TG_TOKEN  = _require("TELEGRAM_BOT_TOKEN")
    TG_CHATID = int(_require("TELEGRAM_CHAT_ID"))
    CLAUDE_KEY = _require("ANTHROPIC_API_KEY")

    log.info("GMC8 — Граф Монте-Крісто ініціалізується...")

    # ── Init components ──
    crypto_scanner    = CryptoScanner()
    freelance_scanner = FreelanceScanner()
    pulse_scanner     = MarketPulseScanner()
    agent             = CountAgent(api_key=CLAUDE_KEY)

    # ── Build Telegram Application ──
    app = Application.builder().token(TG_TOKEN).build()

    # ── Init GMC8 bot ──
    gmc8 = GMC8Bot(
        app=app,
        agent=agent,
        crypto=crypto_scanner,
        freelance=freelance_scanner,
        pulse=pulse_scanner,
        chat_id=TG_CHATID,
    )
    gmc8.register_handlers()

    # ── APScheduler background tasks ──
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        gmc8.run_crypto_scan,
        "interval",
        minutes=30,
        id="crypto_scan",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        gmc8.run_freelance_scan,
        "interval",
        minutes=15,
        id="freelance_scan",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        gmc8.send_morning_pulse,
        "cron",
        hour=9,
        minute=0,
        id="morning_pulse",
        max_instances=1,
    )

    scheduler.start()
    log.info("Scheduler запущено: crypto 30хв | freelance 15хв | pulse 09:00 UTC")

    # ── Start Telegram polling (manual init to control the event loop) ──
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    log.info("GMC8 активний. Граф готовий до роботи.")

    try:
        await asyncio.Event().wait()  # block forever
    except (KeyboardInterrupt, SystemExit):
        log.info("Завершення роботи...")
    finally:
        scheduler.shutdown(wait=False)
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        log.info("GMC8 зупинено.")


if __name__ == "__main__":
    asyncio.run(main())
