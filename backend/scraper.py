from typing import List
from pydantic import BaseModel, HttpUrl
import asyncio
from playwright.async_api import async_playwright
from browserbase import Browserbase
from bs4 import BeautifulSoup
import aiohttp

# Replace with your actual keys or use dotenv
BROWSERBASE_API_KEY = "bb_live_CfggyqxwcPXO_YRf5vEJJS4FMtQ"
BROWSERBASE_PROJECT_ID = "762cf107-8e17-4684-9024-ba1d80c3f963"


class WebsiteContext(BaseModel):
    url: HttpUrl
    title: str
    stylesheets: List[str]
    scripts: List[str]
    images: List[str]
    summary: dict
    css_contents: str  # Added to store downloaded CSS


def extract_important_pieces(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    headings = [tag.get_text(strip=True) for tag in soup.find_all(["h1", "h2", "h3"])]
    buttons = [btn.get_text(strip=True) for btn in soup.find_all("button")]
    links_as_buttons = [
        a.get_text(strip=True) for a in soup.find_all("a") if 'button' in a.get("class", [])
    ]
    nav_links = [
        a.get("href") for nav in soup.find_all("nav")
        for a in nav.find_all("a", href=True)
    ]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    content_paragraphs = [p for p in paragraphs if len(p.split()) > 5]
    section_headers = [tag.get_text(strip=True) for tag in soup.find_all(["section", "article"])]

    return {
        "headings": headings,
        "buttons": buttons + links_as_buttons,
        "nav_links": nav_links,
        "paragraphs": content_paragraphs[:5],
        "section_headers": section_headers
    }


async def download_stylesheets(stylesheet_urls: List[str]) -> str:
    css_contents = []
    async with aiohttp.ClientSession() as session:
        for url in stylesheet_urls:
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        css_contents.append(f"/* {url} */\n{text}")
                    else:
                        css_contents.append(f"/* Failed to load: {url} */")
            except Exception as e:
                css_contents.append(f"/* Error loading {url}: {e} */")
    return "\n\n".join(css_contents)


async def scrape_website(url: str) -> WebsiteContext:
    bb = Browserbase(api_key=BROWSERBASE_API_KEY)
    session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0]

        await page.goto(url)
        title = await page.title()

        stylesheets = await page.eval_on_selector_all(
            'link[rel="stylesheet"]', "els => els.map(e => e.href)"
        )
        scripts = await page.eval_on_selector_all(
            'script[src]', "els => els.map(e => e.src)"
        )
        images = await page.eval_on_selector_all(
            'img[src]', "els => els.map(e => e.src)"
        )
        html = await page.content()
        summary = extract_important_pieces(html)

        css_contents = await download_stylesheets(stylesheets)

        await browser.close()

    return WebsiteContext(
        url=url,
        title=title,
        stylesheets=stylesheets,
        scripts=scripts,
        images=images,
        summary=summary,
        css_contents=css_contents
    )
