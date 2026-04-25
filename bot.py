"""
bot.py
Telegram bot handlers for GMC8 — The Count.
Handles commands, text messages, and proactive alert delivery.
"""
import asyncio
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from agent import CountAgent
from scanners.crypto import CryptoScanner
from scanners.freelance import FreelanceScanner
from scanners.market_pulse import MarketPulseScanner

log = logging.getLogger("bot")

START_MESSAGE = """*Граф Монте-Крісто до вашого прийому.*

Я пройшов через темряву і вийшов з неї з мудрістю, яку не купиш за гроші. Тепер я — ваш провідник у цифровому світі.

Що я вмію:
🔍 Аналізую крипто ф'ючерси (Smart Money, FVG, OB, AMD)
📊 Слідкую за акціями, форексом, золотом, DXY
💼 Знаходжу фріланс можливості (Upwork, Freelancer та інші)
🎯 Будую плани від A до Z для кожної можливості
🧠 Відповідаю на будь-яке питання про цифровий світ

Команди:
/pulse — Ранковий огляд всіх ринків
/hunt — Пошук топ-3 можливостей прямо зараз
/analyze BTC — Глибокий аналіз активу (BTC, ETH, EURUSD, тощо)
/clear — Очистити історію розмови
/help — Показати цю довідку

Або просто напишіть будь-яке питання — я відповім.

_"Вся людська мудрість полягає у двох словах — чекати та сподіватися. Але є третє слово: діяти."_"""

HELP_MESSAGE = """*Можливості Графа:*

*Команди:*
/pulse — Поточний стан ринків + аналіз
/hunt — Топ-3 можливості заробітку прямо зараз
/analyze \[актив\] — Глибокий аналіз (напр: /analyze BTC)
/clear — Очистити пам'ять розмови
/help — Ця довідка

*Автоматичні сповіщення:*
• Крипто сигнали (впевненість ≥70%) — кожні 30 хв
• Фріланс вакансії (Python/AI/боти) — кожні 15 хв
• Ранковий брифінг — щодня о 9:00 UTC

*Просто пишіть:*
Будь-яке питання про крипто, акції, форекс, фріланс, Web3, пасивний дохід — Граф відповість."""


class GMC8Bot:
    def __init__(
        self,
        app: Application,
        agent: CountAgent,
        crypto: CryptoScanner,
        freelance: FreelanceScanner,
        pulse: MarketPulseScanner,
        chat_id: int,
    ):
        self.app = app
        self.agent = agent
        self.crypto = crypto
        self.freelance = freelance
        self.pulse = pulse
        self.chat_id = chat_id
        self._hunting = False

    def register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("clear", self._clear))
        self.app.add_handler(CommandHandler("pulse", self._pulse))
        self.app.add_handler(CommandHandler("hunt", self._hunt))
        self.app.add_handler(CommandHandler("analyze", self._analyze))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._text))

    def _ok(self, update: Update) -> bool:
        return self.chat_id == 0 or update.effective_user.id == self.chat_id

    async def _send(self, chat_id: int, text: str, parse_mode=ParseMode.MARKDOWN):
        """Send a message, splitting if over 4000 chars, with fallback to plain text."""
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=chunk, parse_mode=parse_mode
                )
            except TelegramError:
                try:
                    await self.app.bot.send_message(chat_id=chat_id, text=chunk)
                except TelegramError as e:
                    log.error(f"Send failed: {e}")
            await asyncio.sleep(0.3)

    async def _reply(self, update: Update, text: str):
        """Reply to a user message with markdown, fallback to plain."""
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            except TelegramError:
                try:
                    await update.message.reply_text(chunk)
                except TelegramError as e:
                    log.error(f"Reply failed: {e}")
            await asyncio.sleep(0.3)

    # ── COMMAND HANDLERS ──────────────────────────────────────

    async def _start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        await self._reply(update, START_MESSAGE)

    async def _help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        await self._reply(update, HELP_MESSAGE)

    async def _clear(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        self.agent.clear_history(update.effective_user.id)
        await self._reply(update, "_Пам'ять очищено. Починаємо з чистого аркуша, як нова глава роману._")

    async def _pulse(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        await update.message.reply_text("_Збираю дані ринків..._", parse_mode=ParseMode.MARKDOWN)
        try:
            snapshot = await self.pulse.fetch_snapshot()
            display = self.pulse.format_for_display(snapshot)
            context = self.pulse.format_for_prompt(snapshot)
            analysis = await self.agent.get_pulse_analysis(context)
            await self._reply(update, display + "\n\n" + analysis)
        except Exception as e:
            log.error(f"/pulse error: {e}")
            await self._reply(update, "_Ринкові дані тимчасово недоступні. Спробуйте пізніше._")

    async def _hunt(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        if self._hunting:
            await self._reply(update, "_Рейд вже проводиться. Зачекайте завершення._")
            return
        self._hunting = True
        try:
            await update.message.reply_text(
                "_Граф розпочинає мисливський рейд по всіх ринках..._",
                parse_mode=ParseMode.MARKDOWN
            )
            crypto_snap = self.crypto.get_snapshot()
            pulse_snap = await self.pulse.fetch_snapshot()
            market_context = self.pulse.format_for_prompt(pulse_snap)

            # Build a comprehensive snapshot string
            snapshot_text = market_context + "\n\n"
            if crypto_snap:
                active = [s for s in crypto_snap if s.get("decision") != "NO TRADE"]
                if active:
                    snapshot_text += "КРИПТО СИГНАЛИ:\n"
                    for s in active[:5]:
                        snapshot_text += (
                            f"{'🟢' if s['decision']=='LONG' else '🔴'} {s['symbol']}: "
                            f"{s['decision']} conf={s['confidence']}% RR=1:{s['rr']:.1f}\n"
                        )

            result = await self.agent.hunt(update.effective_user.id, snapshot_text)
            await self._reply(update, result)
        except Exception as e:
            log.error(f"/hunt error: {e}")
            await self._reply(update, "_Рейд завершено з помилкою. Спробуйте ще раз._")
        finally:
            self._hunting = False

    async def _analyze(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        args = ctx.args
        if not args:
            await self._reply(update, "_Вкажіть актив. Приклад: /analyze BTC або /analyze EURUSD_")
            return
        asset = args[0].upper()
        await update.message.reply_text(
            f"_Граф вивчає {asset}..._", parse_mode=ParseMode.MARKDOWN
        )
        try:
            market_data = ""
            # Try crypto first
            if asset in ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"] or asset.endswith("USDT"):
                raw = await self.crypto.analyze_specific(asset)
                if raw:
                    s = raw
                    market_data = (
                        f"LIVE ДАНІ ({asset}):\n"
                        f"Ціна: ${s['entry']:,.4f} | 24h: {s['raw'].get('change', 0):+.2f}%\n"
                        f"Score: {s['raw'].get('score', 0):.1f} | "
                        f"OI 15m: {s['raw'].get('oi_15m', 0):+.1f}% | "
                        f"Funding: {s['raw'].get('funding', 0)*100:.4f}%\n"
                        f"CVD div: {s['raw'].get('cvd_div', 0)} | "
                        f"FVG count: {s['raw'].get('fvg_count', 0)} | "
                        f"OB count: {s['raw'].get('ob_count', 0)}\n"
                        f"Bull sweep: {s['raw'].get('bull_sweep', False)} | "
                        f"Bear sweep: {s['raw'].get('bear_sweep', False)}\n"
                        f"AMD: {s['raw'].get('amd', False)} | Vol ratio: {s['raw'].get('vol_ratio', 1):.2f}\n"
                        f"Поточний сигнал: {s['decision']} (conf={s['confidence']}%)\n"
                        f"Причини: {'; '.join(s.get('reasons', [])[:4])}"
                    )
            # Forex/indices — use pulse scanner
            if not market_data:
                snapshot = await self.pulse.fetch_snapshot()
                context = self.pulse.format_for_prompt(snapshot)
                market_data = context

            analysis = await self.agent.analyze(update.effective_user.id, asset, market_data)
            await self._reply(update, analysis)
        except Exception as e:
            log.error(f"/analyze error: {e}")
            await self._reply(update, f"_Помилка аналізу {asset}. Спробуйте пізніше._")

    async def _text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._ok(update): return
        await ctx.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
        try:
            reply = await self.agent.chat(update.effective_user.id, update.message.text)
            await self._reply(update, reply)
        except Exception as e:
            log.error(f"Text handler error: {e}")
            await self._reply(update, "_Граф на мить задумався... Спробуйте ще раз._")

    # ── PROACTIVE ALERT SENDERS ───────────────────────────────

    async def run_crypto_scan(self):
        """Background task: scan crypto markets, send alerts for new signals ≥70%."""
        try:
            signals = await self.crypto.scan_all()
            for sig in signals:
                text = self._format_crypto_alert(sig)
                await self._send(self.chat_id, text)
                await asyncio.sleep(2)
        except Exception as e:
            log.error(f"Crypto scan error: {e}")

    async def run_freelance_scan(self):
        """Background task: scan freelance RSS, send brief alerts for new jobs."""
        try:
            jobs = await self.freelance.scan_all()
            for job in jobs[:3]:  # max 3 per scan to avoid spam
                text = self._format_freelance_alert(job)
                await self._send(self.chat_id, text)
                await asyncio.sleep(2)
        except Exception as e:
            log.error(f"Freelance scan error: {e}")

    async def send_morning_pulse(self):
        """Daily 9:00 UTC: send market briefing synthesized by Claude."""
        try:
            snapshot = await self.pulse.fetch_snapshot()
            display = self.pulse.format_for_display(snapshot)
            context = self.pulse.format_for_prompt(snapshot)
            analysis = await self.agent.get_pulse_analysis(context)
            full_text = f"*Ранковий брифінг Графа*\n\n{display}\n\n{analysis}"
            await self._send(self.chat_id, full_text)
        except Exception as e:
            log.error(f"Morning pulse error: {e}")

    # ── FORMATTERS ────────────────────────────────────────────

    @staticmethod
    def _format_crypto_alert(sig: dict) -> str:
        direction = sig.get("decision", "")
        symbol = sig.get("symbol", "")
        emoji = "🟢" if direction == "LONG" else "🔴"
        reasons = sig.get("reasons", [])
        reason_text = "\n".join(f"• {r}" for r in reasons[:4])
        return (
            f"{emoji} *{direction}* `{symbol}`\n\n"
            f"💲 Вхід: `${sig['entry']:,.4f}`\n"
            f"🎯 TP: `${sig['tp']:,.4f}` (+{sig['move_pct']:.1f}%)\n"
            f"🛑 SL: `${sig['sl']:,.4f}`\n"
            f"📐 RR: `1:{sig['rr']:.1f}` | Conf: `{sig['confidence']}%`\n"
            f"⚡ Leverage: `{sig['lev']}x` | Strategy: `{sig['strategy']}`\n\n"
            f"{reason_text}"
        )

    @staticmethod
    def _format_freelance_alert(job) -> str:
        title = job.title[:65] + "..." if len(job.title) > 65 else job.title
        return (
            f"{job.source_emoji} *Нова вакансія — {job.source}*\n\n"
            f"📋 {title}\n"
            f"💰 {job.budget}\n"
            f"🔗 [Відкрити]({job.url})"
        )
