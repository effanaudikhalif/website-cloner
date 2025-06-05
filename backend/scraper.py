from typing import List
from pydantic import BaseModel, HttpUrl
import httpx
from urllib.parse import urljoin

BROWSERBASE_API_KEY = "bb_live_CfggyqxwcPXO_YRf5vEJJS4FMtQ"
BROWSERBASE_PROJECT_ID = "762cf107-8e17-4684-9024-ba1d80c3f963"
BROWSERBASE_URL = "https://api.browserbase.com/v1/sessions"


class WebsiteContext(BaseModel):
    url: HttpUrl
    title: str
    stylesheets: List[str]
    css_contents: List[str]
    scripts: List[str]
    images: List[str]


async def scrape_website(url: str) -> WebsiteContext:
    """Fetch the given URL via Browserbase and extract design context."""
    script = """
        return {
            title: document.title,
            stylesheets: Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href),
            scripts: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
            images: Array.from(document.querySelectorAll('img[src]')).map(i => i.src),
            html: document.documentElement.outerHTML,
        };
    """

    headers = {"Authorization": f"Bearer {BROWSERBASE_API_KEY}"}
    payload = {
        "url": url,
        "project_id": BROWSERBASE_PROJECT_ID,
        "scripts": [
            {
                "name": "extractDesignContext",
                "script": script,
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(BROWSERBASE_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()["results"][0]["result"]

        title = data.get("title", "")
        stylesheets = data.get("stylesheets", [])
        scripts = data.get("scripts", [])
        images = data.get("images", [])

        css_contents = []
        for href in stylesheets:
            full_url = urljoin(url, href)
            try:
                css_resp = await client.get(full_url, timeout=10)
                css_resp.raise_for_status()
                css_contents.append(css_resp.text)
            except httpx.HTTPError:
                css_contents.append("")

    return WebsiteContext(
        url=url,
        title=title,
        stylesheets=stylesheets,
        css_contents=css_contents,
        scripts=scripts,
        images=images,
    )
