import json
import re
import sys
from pathlib import Path
import asyncio
import anthropic

from scraper import scrape_website


CONTEXT_FILE = Path(__file__).with_name("context.json")

API_KEY = "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"


def format_prompt(data: dict) -> str:
    """Format website data into a clear prompt for Claude to generate simplified HTML and CSS."""
    return (
        "You are given extracted content and metadata from a website. "
        "Your task is to recreate a simplified, mobile-friendly version of the page using only HTML and custom CSS. "
        "Do not use external JavaScript or CSS frameworks (e.g., Bootstrap, jQuery).\n\n"

        f"Website Title: {data.get('title', '')}\n"
        f"Main Headings: {', '.join(data.get('headings', []))}\n"
        f"Buttons: {', '.join(data.get('buttons', []))}\n"
        f"Navigation Links: {', '.join(data.get('nav_links', []))}\n"
        f"Section Headers: {', '.join(data.get('section_headers', []))}\n"
        f"Image URLs: {', '.join(data.get('images', []))}\n"

        "\nDo not replicate scripts, analytics tags, or third-party stylesheets. "
        "Instead, generate your own modern, minimal, and accessible HTML and CSS code.\n\n"

        "✅ Requirements:\n"
        "- Write mobile-responsive HTML using semantic tags like <header>, <main>, <section>, and <footer>.\n"
        "- Write CSS that covers layout, spacing, typography, image styling, buttons, and navigation.\n"
        "- Make it visually similar to the original site but much simpler and faster to load.\n"
        "- Use a modern, readable sans-serif font.\n"
        "- The output should look polished but minimal.\n\n"

        "🎯 Output format:\n"
        "- Return the full HTML inside a ```html``` fenced code block.\n"
        "- Return the full CSS inside a separate ```css``` fenced code block.\n"
        "- Do not include any commentary or extra text outside the code blocks.\n"
    )

def extract_code(block_type: str, text: str) -> str:
    """Extract a fenced code block of a given type from text."""
    match = re.search(rf"```{block_type}\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else ""


async def main(url: str) -> None:
    """Scrape the given URL, save context.json and generate HTML/CSS."""
    context = await scrape_website(url)
    CONTEXT_FILE.write_text(context.model_dump_json(indent=2))

    data = json.loads(CONTEXT_FILE.read_text())
    prompt = format_prompt(data)

    client = anthropic.Anthropic(api_key=API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )

    text_content = "".join(
        part.text for part in response.content if hasattr(part, "text")
    )

    html = extract_code("html", text_content)
    css = extract_code("css", text_content)

    Path("recreated_page.html").write_text(html)
    Path("styles.css").write_text(css)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))