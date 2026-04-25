"""
scanners/freelance.py
RSS freelance job scanner — ported from AXIFLOW/core/scanner.py
Scans Upwork, Freelancer, PeoplePerHour, Guru for Python/AI/bot jobs.
Sends brief notification alerts only (no auto-execution in GMC8).
"""
import asyncio
import aiohttp
import hashlib
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

log = logging.getLogger("freelance_scanner")

SOURCES = [
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=telegram+bot&sort=recency&paging=0%3B20"},
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=chatgpt+automation&sort=recency&paging=0%3B20"},
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=python+script+automation&sort=recency&paging=0%3B20"},
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=ai+assistant+chatbot&sort=recency&paging=0%3B20"},
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=content+writing+blog&sort=recency&paging=0%3B20"},
    {"name": "Upwork", "emoji": "🔵",
     "url": "https://www.upwork.com/ab/feed/jobs/rss?q=web+scraping+data+extraction&sort=recency&paging=0%3B20"},
    {"name": "Freelancer", "emoji": "🟢",
     "url": "https://www.freelancer.com/rss/jobs/telegram-bot.xml"},
    {"name": "Freelancer", "emoji": "🟢",
     "url": "https://www.freelancer.com/rss/jobs/chatgpt.xml"},
    {"name": "Freelancer", "emoji": "🟢",
     "url": "https://www.freelancer.com/rss/jobs/python.xml"},
    {"name": "Freelancer", "emoji": "🟢",
     "url": "https://www.freelancer.com/rss/jobs/content-writing.xml"},
    {"name": "Freelancer", "emoji": "🟢",
     "url": "https://www.freelancer.com/rss/jobs/data-entry.xml"},
    {"name": "PeoplePerHour", "emoji": "🟡",
     "url": "https://www.peopleperhour.com/rss/jobs?q=chatgpt+bot+automation"},
    {"name": "PeoplePerHour", "emoji": "🟡",
     "url": "https://www.peopleperhour.com/rss/jobs?q=python+script+ai"},
    {"name": "Guru", "emoji": "🟠",
     "url": "https://www.guru.com/jobs/search/index.aspx?output=rss&keyword=telegram+bot+chatgpt"},
    {"name": "Guru", "emoji": "🟠",
     "url": "https://www.guru.com/jobs/search/index.aspx?output=rss&keyword=python+automation+script"},
]

CAN_DO = [
    "telegram bot", "discord bot", "chatbot", "chat bot",
    "python script", "automation script", "automate",
    "chatgpt", "openai", "claude ai", "gpt", "llm", "ai assistant",
    "content writ", "copywriting", "blog post", "article writ",
    "product description", "social media", "instagram caption",
    "web scraping", "data scraping", "data extraction", "crawler", "parser",
    "google sheets", "excel automation", "spreadsheet",
    "resume", "cover letter", "proofreading", "rewrite",
    "translation", "translate",
    "data entry", "data processing", "data analysis",
    "landing page", "html", "simple website", "react component",
    "email template", "newsletter",
    "summarize", "summary", "report generat",
    "virtual assistant", "va task",
    "api integration", "webhook", "zapier",
    "text classification", "sentiment analysis",
]

CANT_DO = [
    "mobile app", "ios", "android", "flutter", "react native", "swift", "kotlin",
    "blockchain", "smart contract", "solidity", "web3", "nft",
    "machine learning", "train model", "deep learning", "neural network", "pytorch", "tensorflow",
    "3d model", "blender", "unity", "unreal", "game dev",
    "video edit", "motion graphic", "after effects", "premiere",
    "logo design", "graphic design", "illustrator", "photoshop",
    "wordpress plugin", "magento", "shopify app", "woocommerce plugin",
    "database architect", "devops", "kubernetes", "docker swarm",
    "cybersecurity", "penetration test", "exploit",
]


@dataclass
class RawJob:
    title: str
    description: str
    url: str
    source: str
    source_emoji: str
    budget: str = "Не вказано"
    uid: str = ""
    found_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.uid = hashlib.md5(self.url.encode()).hexdigest()[:10]
        self.description = re.sub(r'<[^>]+>', ' ', self.description)
        self.description = re.sub(r'\s+', ' ', self.description).strip()[:600]


class FreelanceScanner:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.seen: set = set()

    async def _fetch(self, url: str) -> Optional[str]:
        try:
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession(headers={
                    "User-Agent": "Mozilla/5.0 (compatible; RSS Reader)",
                    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
                })
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status == 200:
                    return await r.text()
                if r.status == 429:
                    await asyncio.sleep(20)
        except Exception as e:
            log.debug(f"Fetch {url[:60]}: {e}")
        return None

    def _parse_rss(self, xml: str, source: dict) -> list[RawJob]:
        jobs = []
        try:
            import feedparser
            feed = feedparser.parse(xml)
            for e in feed.entries[:20]:
                title = e.get("title", "").strip()
                desc  = e.get("summary", e.get("description", "")).strip()
                url   = e.get("link", "")
                if not title or not url:
                    continue
                budget = self._find_budget(title + " " + desc)
                jobs.append(RawJob(
                    title=title, description=desc, url=url, budget=budget,
                    source=source["name"], source_emoji=source["emoji"],
                ))
        except Exception as ex:
            log.debug(f"RSS parse: {ex}")
        return jobs

    @staticmethod
    def _find_budget(text: str) -> str:
        for pat in [
            r'\$\s*[\d,]+\s*[-–]\s*\$\s*[\d,]+',
            r'\$\s*[\d,]+\+?',
            r'£\s*[\d,]+',
            r'€\s*[\d,]+',
            r'[\d,]+\s*USD',
            r'Budget[:\s]+\$?[\d,]+',
        ]:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(0).strip()
        return "Не вказано"

    def _is_doable(self, job: RawJob) -> bool:
        text = (job.title + " " + job.description).lower()
        for kw in CANT_DO:
            if kw in text:
                return False
        for kw in CAN_DO:
            if kw in text:
                return True
        return False

    async def scan_all(self) -> list[RawJob]:
        """Scan all RSS feeds, return new doable jobs not seen before."""
        new_jobs: list[RawJob] = []
        for src in SOURCES:
            xml = await self._fetch(src["url"])
            if xml:
                jobs = self._parse_rss(xml, src)
                for j in jobs:
                    if j.uid not in self.seen and self._is_doable(j):
                        self.seen.add(j.uid)
                        new_jobs.append(j)
            await asyncio.sleep(1.5)
        log.info(f"Freelance скан: {len(new_jobs)} нових підходящих вакансій")
        return new_jobs
