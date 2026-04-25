"""
scanners/market_pulse.py
Daily market pulse — fetches prices and 24h changes for key assets
using yfinance (free, no API key required).
"""
import asyncio
import logging

log = logging.getLogger("market_pulse")

PULSE_TICKERS = {
    "SPY":       "S&P 500",
    "BTC-USD":   "Bitcoin",
    "ETH-USD":   "Ethereum",
    "GC=F":      "Gold",
    "DX-Y.NYB":  "DXY (USD Index)",
    "EURUSD=X":  "EUR/USD",
    "^VIX":      "VIX (Fear)",
}


class MarketPulseScanner:
    def __init__(self):
        self.last_snapshot: dict = {}

    async def fetch_snapshot(self) -> dict:
        """Fetch current prices and 24h changes for all pulse tickers."""
        def _fetch_sync():
            try:
                import yfinance as yf
            except ImportError:
                log.error("yfinance not installed")
                return {}

            result = {}
            for ticker, name in PULSE_TICKERS.items():
                try:
                    t = yf.Ticker(ticker)
                    hist = t.history(period="2d", interval="1d")
                    if len(hist) >= 2:
                        price = float(hist["Close"].iloc[-1])
                        prev  = float(hist["Close"].iloc[-2])
                        change_pct = (price - prev) / prev * 100
                        result[ticker] = {
                            "name":       name,
                            "price":      round(price, 4),
                            "change_pct": round(change_pct, 2),
                            "direction":  "📈" if change_pct >= 0 else "📉",
                        }
                    elif len(hist) == 1:
                        price = float(hist["Close"].iloc[-1])
                        result[ticker] = {
                            "name":       name,
                            "price":      round(price, 4),
                            "change_pct": 0.0,
                            "direction":  "➡️",
                        }
                except Exception as e:
                    log.debug(f"yfinance {ticker}: {e}")
            return result

        snapshot = await asyncio.to_thread(_fetch_sync)
        if snapshot:
            self.last_snapshot = snapshot
        return snapshot or self.last_snapshot

    def format_for_prompt(self, snapshot: dict) -> str:
        """Format snapshot as a context string for Claude analysis."""
        if not snapshot:
            return "Ринкові дані тимчасово недоступні."
        lines = ["ПОТОЧНИЙ СТАН РИНКІВ:"]
        for ticker, data in snapshot.items():
            lines.append(
                f"{data['direction']} {data['name']} ({ticker}): "
                f"{data['price']:,.4f} ({data['change_pct']:+.2f}% за 24h)"
            )
        return "\n".join(lines)

    def format_for_display(self, snapshot: dict) -> str:
        """Format snapshot as a human-readable Telegram message block."""
        if not snapshot:
            return "_Ринкові дані тимчасово недоступні_"
        lines = ["*Ринковий пульс:*\n"]
        for ticker, data in snapshot.items():
            sign = "+" if data["change_pct"] >= 0 else ""
            lines.append(
                f"{data['direction']} *{data['name']}*: `{data['price']:,.4f}` "
                f"({sign}{data['change_pct']:.2f}%)"
            )
        return "\n".join(lines)
