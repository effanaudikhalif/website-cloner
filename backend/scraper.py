# backend/scraper.py

from typing import List
from pydantic import BaseModel, HttpUrl
import asyncio
from playwright.async_api import async_playwright
from browserbase import Browserbase
from bs4 import BeautifulSoup
import aiohttp

BROWSERBASE_API_KEY = "bb_live_CfggyqxwcPXO_YRf5vEJJS4FMtQ"
BROWSERBASE_PROJECT_ID = "762cf107-8e17-4684-9024-ba1d80c3f963"

class WebsiteContext(BaseModel):
    url: HttpUrl
    title: str
    stylesheets: List[str]
    scripts: List[str]
    images: List[str]
    summary: dict
    css_contents: str
    html: str

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
    layout_classes = list(set(
        cls for tag in soup.find_all(["div", "section"]) if tag.get("class")
        for cls in tag.get("class")
    ))
    used_ids = [tag.get("id") for tag in soup.find_all(attrs={"id": True})]

    summary = {
        "headings": headings,
        "buttons": buttons + links_as_buttons,
        "nav_links": nav_links,
        "paragraphs": content_paragraphs[:5],
        "section_headers": section_headers,
        "layout_classes": layout_classes[:20],
        "ids": used_ids[:20],
    }

    print("\n[DEBUG] Extracted Summary:")
    for key, val in summary.items():
        print(f"  {key}: {val[:3]}{'...' if len(val) > 3 else ''}")  # Preview first few items

    return summary

async def download_stylesheets(stylesheet_urls: List[str]) -> str:
    css_contents = []
    print("\n[DEBUG] Downloading stylesheets...")
    async with aiohttp.ClientSession() as session:
        for url in stylesheet_urls:
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        css_contents.append(text)
                        print(f"  ✅ Downloaded: {url}")
                    else:
                        print(f"  ❌ Failed ({response.status}): {url}")
            except Exception as e:
                print(f"  ❌ Error downloading {url}: {e}")
    return "\n\n".join(css_contents)

async def scrape_website(url: str) -> WebsiteContext:
    print(f"\n[DEBUG] Starting scrape for: {url}")
    bb = Browserbase(api_key=BROWSERBASE_API_KEY)
    session = bb.sessions.create(project_id=BROWSERBASE_PROJECT_ID)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0]

        await page.goto(url)
        print("[DEBUG] Page loaded.")

        title = await page.title()
        print(f"[DEBUG] Page title: {title}")

        stylesheets = await page.eval_on_selector_all(
            'link[rel="stylesheet"]', "els => els.map(e => e.href)"
        )
        print(f"[DEBUG] Stylesheets found: {len(stylesheets)}")

        scripts = await page.eval_on_selector_all(
            'script[src]', "els => els.map(e => e.src)"
        )
        print(f"[DEBUG] Script tags found: {len(scripts)}")

        images = await page.eval_on_selector_all(
            'img[src]', "els => els.map(e => e.src)"
        )
        print(f"[DEBUG] Images found: {len(images)}")

        html = await page.content()
        print(f"[DEBUG] HTML content length: {len(html)}")

        summary = extract_important_pieces(html)
        css_contents = await download_stylesheets(stylesheets)

        await browser.close()
        print("[DEBUG] Browser closed.")

    return WebsiteContext(
        url=url,
        title=title,
        stylesheets=stylesheets,
        scripts=scripts,
        images=images,
        summary=summary,
        css_contents=css_contents,
        html=html,
    )
