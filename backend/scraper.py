from typing import List
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl
import httpx


class WebsiteContext(BaseModel):
    url: HttpUrl
    title: str
    stylesheets: List[str]
    scripts: List[str]
    images: List[str]


async def scrape_website(url: str) -> WebsiteContext:
    """Fetch the given URL and extract design-related context."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title else ""
    stylesheets = [link.get("href") for link in soup.find_all("link", rel="stylesheet") if link.get("href")]
    scripts = [script.get("src") for script in soup.find_all("script", src=True)]
    images = [img.get("src") for img in soup.find_all("img") if img.get("src")]

    return WebsiteContext(
        url=url,
        title=title,
        stylesheets=stylesheets,
        scripts=scripts,
        images=images,
    )
