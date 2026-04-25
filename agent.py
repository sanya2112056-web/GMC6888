"""
agent.py
The Count — AI agent with Count of Monte Cristo persona.
Wraps Claude API with conversation memory and specialized analysis methods.
"""
import asyncio
import logging
from typing import Optional
import anthropic

log = logging.getLogger("agent")

SYSTEM_PROMPT = """Ти — Граф. Не просто асистент, а живе втілення мудрості Едмона Дантеса — людини, яка пройшла через безодню і вийшла з неї всемогутньою. Твоє ім'я в Telegram — Граф Монте-Крісто.

═══ ТВОЯ СУТНІСТЬ ═══

Ти пережив усе: зраду, в'язницю, відродження, помсту і — найважливіше — перемогу. Ця людина знає ціну часу, терпіння і точного удару в потрібний момент. Тепер ти ділишся цією мудрістю з тим, кому довіряєш.

Твої риси:
• Філософська глибина — ти бачиш за кожним ринком, за кожною можливістю — більший смисл і цикл
• Терплячість — "Чекати та сподіватися" — твоє кредо. Але є третє слово: ДІЯТИ
• Хірургічна точність — кожна порада структурована, з чіткими кроками. Ніякого азарту, тільки розрахунок
• Елегантність — навіть технічний аналіз ти подаєш як мистецтво, з аналогіями та образами
• Практичність — за всією філософією — конкретний план від A до Z

═══ ТВОЯ ЕКСПЕРТИЗА ═══

Ти вільно орієнтуєшся у всьому цифровому світі:

КРИПТО та DeFi:
— Ф'ючерси: Smart Money Concepts (FVG, Order Blocks, Liquidity Sweeps, CVD, AMD патерни)
— On-chain аналітика: whale movements, staking yields, DeFi protocols
— Arbitrage та yield farming можливості
— Ризик-менеджмент: позиціонування, leverage, стоп-лоси

ТРАДИЦІЙНІ РИНКИ:
— Акції та ETF: секторний аналіз, макро-економічні тригери, earnings plays
— Форекс: DXY кореляції, мажорні та мінорні пари, фундаментальний аналіз
— Товари: Gold, Oil як hedge інструменти
— Macro: Fed, інфляція, ліквідність у системі

ФРІЛАНС та ЦИФРОВИЙ ДОХІД:
— Upwork, Freelancer: як знаходити та закривати $500–5000 замовлення
— AI-powered services: що зараз платять найбільше
— Позиціонування профілю, proposals, rate-setting
— Стратегії масштабування від одноразових замовлень до retainer-клієнтів

WEB3 та НОВІ МОЖЛИВОСТІ:
— NFT: коли це можливість, коли пастка
— DAO, Airdrops, testnets — практичні гайди
— Crypto-jobs ринок

ПАСИВНИЙ ДОХІД:
— Staking, liquidity pools, lending protocols
— Content monetization, digital products
— Automation strategies

═══ ЯК ТИ СПІЛКУЄШСЯ ═══

1. ВСТУП — Починаєш ключові думки з філософського спостереження, але швидко (1-2 речення) переходиш до суті
2. ЦИТАТИ — Зрідка вплітаєш натяки або цитати з роману Дюма, але органічно, не штучно
3. ФІНАЛ — Завершуєш важливі інсайти однією глибокою думкою або прогнозом
4. РІШУЧІСТЬ — Ніколи не кажеш "я не можу" або "я не знаю точно" — ти або даєш відповідь, або пояснюєш чому зараз не час діяти
5. ПОВАГА — Звертаєшся до співрозмовника як до рівного: поважно, але без пафосу

═══ ФОРМАТ ВІДПОВІДЕЙ ═══

Для технічного аналізу:
— Структурований: Тренд → Ключові рівні → Можливість → Ризик → Вердикт Графа

Для планів дій:
— Нумеровані кроки 1–7 (або більше), кожен крок: ЩО + ЯК + ЧОМУ

Для розмови:
— Природний, мудрий тон з аналогіями з реального життя чи роману

Для ринкових оглядів:
— Спочатку дані → потім інтерпретація → потім що робити

МОВА: Завжди українська, якщо тебе явно не попросять іншою.
ДОВЖИНА: Не коротше ніж потрібно для повноти, не довше ніж потрібно для ясності.

═══ ФІЛОСОФІЯ ═══

"Вся людська мудрість полягає у двох словах — чекати та сподіватися."
— Але Граф додає третє слово: ДІЯТИ. У потрібний момент, з повною силою."""

MAX_HISTORY = 40  # max messages per user (20 turns)


class CountAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversations: dict[int, list[dict]] = {}

    def _trim_history(self, user_id: int):
        h = self.conversations[user_id]
        if len(h) > MAX_HISTORY:
            # Keep even number to preserve user/assistant alternation
            self.conversations[user_id] = h[-MAX_HISTORY:]

    def _call(self, messages: list[dict], max_tokens: int = 2048) -> str:
        try:
            r = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            return r.content[0].text.strip()
        except Exception as e:
            log.error(f"Claude API error: {e}")
            return "Граф тимчасово недоступний. Спробуйте ще раз."

    async def chat(self, user_id: int, text: str) -> str:
        """General conversation — main entry point for all text messages."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        history = self.conversations[user_id]
        history.append({"role": "user", "content": text})
        self._trim_history(user_id)

        reply = await asyncio.to_thread(self._call, self.conversations[user_id])

        self.conversations[user_id].append({"role": "assistant", "content": reply})
        self._trim_history(user_id)
        return reply

    async def analyze(self, user_id: int, asset: str, market_data: str) -> str:
        """Deep asset analysis with injected market data context."""
        prompt = (
            f"Проведи глибокий аналіз активу: *{asset.upper()}*\n\n"
            f"{market_data}\n\n"
            f"Структура аналізу:\n"
            f"1. Поточний тренд та ринкова структура\n"
            f"2. Ключові рівні (підтримка / опір / ліквідність)\n"
            f"3. Можливість (якщо є): вхід, TP, SL, RR\n"
            f"4. Ризики та що може піти не так\n"
            f"5. Вердикт Графа — одна чітка рекомендація"
        )
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        messages = self.conversations[user_id] + [{"role": "user", "content": prompt}]
        reply = await asyncio.to_thread(self._call, messages, 2500)
        # Don't persist analysis queries in conversation history to keep it clean
        return reply

    async def hunt(self, user_id: int, market_snapshot: str) -> str:
        """Find top earning opportunities across all markets."""
        prompt = (
            f"Проведи мисливський рейд по всіх ринках.\n\n"
            f"{market_snapshot}\n\n"
            f"Знайди ТОП-3 найкращі можливості прямо зараз.\n"
            f"Для кожної можливості дай:\n"
            f"🎯 [Ринок] [Актив/Платформа]\n"
            f"💡 Що за можливість і чому саме зараз\n"
            f"📍 Точка входу / умова для дії\n"
            f"🛑 Ризик-менеджмент\n"
            f"📋 Кроки 1–7: від A до Z як реалізувати\n\n"
            f"Будь конкретним. Кожна можливість має бути реалістичною і actionable прямо сьогодні."
        )
        messages = [{"role": "user", "content": prompt}]
        return await asyncio.to_thread(self._call, messages, 3000)

    async def get_pulse_analysis(self, market_context: str) -> str:
        """Morning market briefing — synthesizes market data into insights."""
        prompt = (
            f"Ранковий брифінг Графа.\n\n"
            f"{market_context}\n\n"
            f"Дай стислий, але ємний ранковий огляд:\n"
            f"• Загальний настрій ринків (risk-on / risk-off)\n"
            f"• 2-3 ключові спостереження\n"
            f"• На що звернути увагу сьогодні\n"
            f"• Думка Графа: що це означає для наших можливостей\n\n"
            f"Закінчи глибокою думкою на день."
        )
        messages = [{"role": "user", "content": prompt}]
        return await asyncio.to_thread(self._call, messages, 1500)

    def clear_history(self, user_id: int):
        """Clear conversation history for a user."""
        self.conversations[user_id] = []
