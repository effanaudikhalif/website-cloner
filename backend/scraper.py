# backend/scraper.py

from typing import List
from pydantic import BaseModel, HttpUrl
import asyncio
from playwright.async_api import async_playwright
from browserbase import Browserbase
from bs4 import BeautifulSoup
import aiohttp
import os
from dotenv import load_dotenv
import trafilatura  # Add at the top with other imports
from summarize_utils import chunk_text, summarize_chunks  # Add at the top with other imports

load_dotenv()

class WebsiteContext(BaseModel):
    url: HttpUrl
    stylesheets: List[str]
    scripts: List[str]
    images: List[str]
    summary: dict
    css_contents: str
    html: str

def extract_important_pieces(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # --- FIX: Use trafilatura.extract to get main content as plain text ---
    main_content_text = trafilatura.extract(html, include_comments=False, include_tables=True)
    main_content_html = None  # Not available directly from trafilatura

    # --- NEW: Chunk and summarize the main content text ---
    main_content_chunks = []
    main_content_summaries = []
    if main_content_text:
        main_content_chunks = chunk_text(main_content_text, max_words=200)
        main_content_summaries = summarize_chunks(main_content_chunks)

    # Fallback: use full HTML if trafilatura fails
    content_source = soup

    headings = [tag.get_text(strip=True) for tag in content_source.find_all(["h1", "h2", "h3"])]
    buttons = [btn.get_text(strip=True) for btn in content_source.find_all("button")]
    links_as_buttons = [
        a.get_text(strip=True) for a in content_source.find_all("a") if 'button' in a.get("class", [])
    ]
    nav_links = [
        a.get("href") for nav in content_source.find_all("nav")
        for a in nav.find_all("a", href=True)
    ]
    paragraphs = [p.get_text(strip=True) for p in content_source.find_all("p")]
    content_paragraphs = [p for p in paragraphs if len(p.split()) > 5]
    section_headers = [tag.get_text(strip=True) for tag in content_source.find_all(["section", "article"])]
    layout_classes = list(set(
        cls for tag in content_source.find_all(["div", "section"]) if tag.get("class")
        for cls in tag.get("class")
    ))
    used_ids = [tag.get("id") for tag in content_source.find_all(attrs={"id": True})]

    # --- ENHANCED: Extract all images with src, alt, and parent context ---
    images_detailed = []
    for img in content_source.find_all("img"):
        parent = img.find_parent(["section", "div", "article", "header", "footer"])
        images_detailed.append({
            "src": img.get("src"),
            "alt": img.get("alt"),
            "parent_tag": parent.name if parent else None,
            "parent_classes": parent.get("class", []) if parent else [],
        })

    # --- ENHANCED: Extract all buttons and links with text, class, style ---
    buttons_detailed = []
    for btn in content_source.find_all("button"):
        buttons_detailed.append({
            "text": btn.get_text(strip=True),
            "class": btn.get("class", []),
            "style": btn.get("style", "")
        })
    links_detailed = []
    for a in content_source.find_all("a"):
        links_detailed.append({
            "text": a.get_text(strip=True),
            "href": a.get("href"),
            "class": a.get("class", []),
            "style": a.get("style", "")
        })

    # --- ENHANCED: Attempt to detect testimonial/card sections ---
    testimonials = []
    for card in content_source.find_all(["section", "div", "article"]):
        classes = card.get("class", [])
        if any("testimonial" in c or "review" in c or "card" in c for c in classes):
            quote = card.get_text(" ", strip=True)
            author = None
            author_img = None
            # Try to find author and avatar inside the card
            author_tag = card.find(["span", "div", "p"], class_=lambda c: c and ("author" in c or "name" in c))
            if author_tag:
                author = author_tag.get_text(strip=True)
            img_tag = card.find("img")
            if img_tag:
                author_img = img_tag.get("src")
            testimonials.append({
                "quote": quote,
                "author": author,
                "avatar": author_img,
                "classes": classes
            })

    summary = {
        "headings": headings,
        "buttons": buttons + links_as_buttons,
        "nav_links": nav_links,
        "paragraphs": content_paragraphs[:5],
        "section_headers": section_headers,
        "layout_classes": layout_classes[:20],
        "ids": used_ids[:20],
        # --- NEW: Add main content and text ---
        "main_content_html": main_content_html,
        "main_content_text": main_content_text,
        # --- NEW: Add chunks and summaries ---
        "main_content_chunks": main_content_chunks,
        "main_content_summaries": main_content_summaries,
        # --- ENHANCED: Add detailed images, buttons, links, testimonials ---
        "images_detailed": images_detailed,
        "buttons_detailed": buttons_detailed,
        "links_detailed": links_detailed,
        "testimonials": testimonials,
    }

    print("\n[DEBUG] Extracted Summary:")
    for key, val in summary.items():
        if isinstance(val, list):
            print(f"  {key}: {val[:3]}{'...' if len(val) > 3 else ''}")  # Preview first few items
        else:
            print(f"  {key}: {str(val)[:60]}{'...' if val and len(str(val)) > 60 else ''}")

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
    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0]

        # --- 1. Wait for full page load (network idle or body selector) ---
        try:
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_selector("body", timeout=10000)
            print("[DEBUG] Page loaded and body present.")
        except Exception as e:
            print(f"[ERROR] Page load failed: {e}")
            await browser.close()
            raise

        # --- 2. Attempt to dismiss popups/cookie banners (common selectors) ---
        popup_selectors = [
            '[id*="cookie"] button', '[class*="cookie"] button', '[id*="consent"] button', '[class*="consent"] button',
            '[aria-label*="close"]', '.close', '.modal-close', '.popup-close', '[data-dismiss]'
        ]
        for sel in popup_selectors:
            try:
                if await page.query_selector(sel):
                    await page.click(sel, timeout=2000)
                    print(f"[DEBUG] Dismissed popup/banner with selector: {sel}")
            except Exception:
                pass  # Ignore if not found or not clickable

        # --- 3. Optional: Save screenshot for debugging ---
        try:
            screenshot_path = f"generated/screenshot_{os.getpid()}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[DEBUG] Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"[WARNING] Could not save screenshot: {e}")

        # --- 4. Retry logic for extracting content ---
        retries = 2
        for attempt in range(retries + 1):
            try:
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
            except Exception as e:
                print(f"[ERROR] Attempt {attempt+1} failed: {e}")
                if attempt == retries:
                    await browser.close()
                    raise
                await asyncio.sleep(2)  # Wait before retrying
