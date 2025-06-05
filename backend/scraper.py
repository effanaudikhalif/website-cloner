from pydantic import BaseModel, HttpUrl
from typing import List
import asyncio
from playwright.async_api import async_playwright
from browserbase import Browserbase

# Replace these with your actual values
BROWSERBASE_API_KEY = "bb_live_CfggyqxwcPXO_YRf5vEJJS4FMtQ"
BROWSERBASE_PROJECT_ID = "762cf107-8e17-4684-9024-ba1d80c3f963"

class WebsiteContext(BaseModel):
    url: HttpUrl
    title: str
    html: str
    stylesheets: List[str]
    scripts: List[str]
    images: List[str]

async def scrape_website(url: str) -> WebsiteContext:
    bb = Browserbase(api_key=BROWSERBASE_API_KEY)
    session = await asyncio.to_thread(bb.sessions.create, project_id=BROWSERBASE_PROJECT_ID)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0]

        await page.goto(url, timeout=30000)
        title = await page.title()
        html = await page.content()

        stylesheets = await page.eval_on_selector_all(
            'link[rel="stylesheet"]',
            "els => els.map(e => e.href)"
        )
        scripts = await page.eval_on_selector_all(
            'script[src]',
            "els => els.map(e => e.src)"
        )
        images = await page.eval_on_selector_all(
            'img[src]',
            "els => els.map(e => e.src)"
        )

        await browser.close()

    return WebsiteContext(
        url=url,
        title=title,
        html=html,
        stylesheets=stylesheets,
        scripts=scripts,
        images=images,
    )
