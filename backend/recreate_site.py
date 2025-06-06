# backend/recreate_site.py

import json
import re
import sys
from pathlib import Path
import asyncio
import anthropic

from scraper import scrape_website
from filter_css import filter_css_from_html_and_css

# Where to dump the scraped context (full HTML, raw CSS, summary, etc.)
CONTEXT_FILE = Path(__file__).with_name("context.json")

# Your Anthropic API key
API_KEY = "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"


def build_summary_and_minimal_html(context: dict) -> (dict, str):
    """
    From the full scraped context, build:
      1) A JSON ‘summary’ that lists exact headings, nav link labels/URLs, hero text, and card headings.
      2) A minimal HTML snippet containing:
         • <header>…</header> with exact site title and nav links
         • <section class="hero">…</section> containing the hero image, hero heading, and subheading
         • <section class="news-cards">…</section> containing exactly three <article> news-card stubs
         • <footer>…</footer> containing up to 4 footer links
    """
    summary = {}
    title = context.get("title", "")

    # 1) NAV LINKS with exact label/text and href
    nav_links = []
    for href in context.get("summary", {}).get("nav_links", [])[:5]:
        # Derive a “label” from the URL path if possible (e.g. "/admissions" → "Admissions")
        label = href.rstrip("/").split("/")[-1].replace("-", " ").title() or href
        nav_links.append({"href": href, "label": label})
    summary["nav_links"] = nav_links

    # 2) HERO – we’ll assume the first <img> found in the full HTML is the hero image
    #    and the first scraped heading is the hero heading. Subheading = first paragraph.
    hero_img = context.get("images", [None])[0] or ""
    hero_heading = context.get("summary", {}).get("headings", [""])[0]
    paragraphs = context.get("summary", {}).get("paragraphs", [])
    hero_subheading = paragraphs[0] if paragraphs else ""
    summary["hero"] = {
        "img": hero_img,
        "heading": hero_heading,
        "subheading": hero_subheading,
        "button_text": "Explore BU"
    }

    # 3) NEWS CARDS – take up to 3 scraped section_headers (assuming they correspond to card headings)
    cards = []
    for header in context.get("summary", {}).get("section_headers", [])[:3]:
        cards.append({
            "heading": header,
            "snippet": "Preview text..."
        })
    summary["news_cards"] = cards

    # 4) FOOTER LINKS – take up to 4 from nav_links as placeholders
    footer_links = []
    for entry in nav_links[:4]:
        footer_links.append({"label": entry["label"], "href": entry["href"]})
    summary["footer_links"] = footer_links

    # Now build the minimal HTML snippet:
    parts = []

    # ---------- HEADER + NAV ----------
    parts.append("<header class=\"site-header\">")
    parts.append(f"  <h1>{title}</h1>")
    if nav_links:
        parts.append("  <nav class=\"main-nav\">")
        parts.append("    <ul>")
        for link in nav_links:
            parts.append(f"      <li><a href=\"{link['href']}\">{link['label']}</a></li>")
        parts.append("    </ul>")
        parts.append("  </nav>")
    parts.append("</header>")

    # ---------- HERO ----------
    parts.append("<section class=\"hero\">")
    parts.append(f"  <img src=\"{hero_img}\" alt=\"{hero_heading}\">")
    parts.append("  <div class=\"hero-text\">")
    parts.append(f"    <h2>{hero_heading}</h2>")
    parts.append(f"    <p>{hero_subheading}</p>")
    parts.append(f"    <button>{summary['hero']['button_text']}</button>")
    parts.append("  </div>")
    parts.append("</section>")

    # ---------- NEWS CARDS (3) ----------
    parts.append("<section class=\"news-cards\">")
    parts.append("  <div class=\"news-grid\">")
    for card in cards:
        parts.append("    <article class=\"news-card\">")
        parts.append(f"      <h3>{card['heading']}</h3>")
        parts.append(f"      <p>{card['snippet']}</p>")
        parts.append("      <a href=\"#\" class=\"read-more\">Read More</a>")
        parts.append("    </article>")
    parts.append("  </div>")
    parts.append("</section>")

    # ---------- FOOTER ----------
    parts.append("<footer class=\"site-footer\">")
    parts.append("  <div class=\"footer-links\">")
    parts.append("    <ul>")
    for link in footer_links:
        parts.append(f"      <li><a href=\"{link['href']}\">{link['label']}</a></li>")
    parts.append("    </ul>")
    parts.append("  </div>")
    parts.append("</footer>")

    minimal_html = "\n".join(parts)
    return summary, minimal_html


def build_critical_css(filtered_css: str) -> str:
    """
    From the “filtered_css” (which already only contains selectors that appear
    anywhere in the full HTML), further reduce to a tiny set of “critical” rules:
      • body, h1‐h3, a, button
      • .site-header, .main-nav, .hero, .hero img, .hero-text, .news-cards,
        .news-grid, .news-card, .read-more, .site-footer, .footer-links
    """
    # We’ll look for any rule whose selector matches one of these critical substrings:
    critical_selectors = [
        r"\bbody\b",
        r"\bh1\b", r"\bh2\b", r"\bh3\b", r"\ba\b", r"\bbutton\b",
        r"\.site-header\b",
        r"\.main-nav\b",
        r"\.hero\b", 
        r"\.hero\s+img\b", 
        r"\.hero-text\b", 
        r"\.news-cards\b",
        r"\.news-grid\b",
        r"\.news-card\b",
        r"\.read-more\b",
        r"\.site-footer\b",
        r"\.footer-links\b"
    ]

    # Break the filtered_css into individual rules: we assume “selector { ... }”
    rules = re.findall(r"([^{]+\{[^}]*\})", filtered_css, re.DOTALL)

    critical_rules = []
    for rule in rules:
        selector_part = rule.split("{", 1)[0].strip()
        # If any critical pattern appears in selector_part, keep the rule
        for pat in critical_selectors:
            if re.search(pat, selector_part):
                critical_rules.append(rule.strip())
                break

    return "\n\n".join(critical_rules).strip()


def format_prompt(min_html: str, summary: dict, critical_css: str) -> str:
    """
    Build the final prompt to send to Claude:
      1) We include a little JSON summary with exact link labels, headings, button text.
      2) We embed the minimal HTML snippet (```html```).
      3) We embed the small critical CSS snippet (```css```).
      4) We instruct Claude to return exactly two fences: ```html``` and ```css```.
    """
    # 1) JSON summary block
    summary_json = json.dumps(summary, indent=2)

    return (
        "You are given a JSON summary, a minimal HTML snippet, and a small critical CSS snippet.\n"
        "Recreate a full, responsive, semantic HTML/CSS page that visually resembles the original "
        "website as closely as possible. Do not include any JavaScript or external CSS frameworks.\n\n"
        "❗️ Return exactly two fenced code blocks:\n"
        "   • One ```html``` containing the complete page markup\n"
        "   • One ```css``` containing the complete stylesheet\n\n"
        "Below is the JSON summary (use these exact labels, headings, and URLs):\n"
        f"```json\n{summary_json}\n```\n\n"
        "Below is the minimal HTML snippet:\n"
        f"```html\n{min_html}\n```\n\n"
        "Below is the critical CSS snippet:\n"
        f"```css\n{critical_css}\n```\n\n"
        "✅ Requirements:\n"
        "- Use <header>, <nav>, <main>, <section>, <footer> semantically.\n"
        "- Make it mobile-first (responsive).\n"
        "- Use the provided CSS rules to guide layout, colors, typography, and button styles.\n"
        "- Choose a modern sans-serif font.\n"
        "- Keep it minimal and clean, but replicate the brand look and feel.\n"
    )


def extract_code(block_type: str, text: str) -> str:
    """
    Extract a fenced ```block_type``` code block from Claude’s output.
    If the CSS fence never closes, capture everything from the opening ```css``` to end of output.
    """
    # 1) Try to find a fully fenced block
    fence_pattern = rf"```{block_type}\s*(.*?)\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        print(f"[DEBUG] Extracted full {block_type} block (length {len(content)})")
        return content

    # 2) If block_type == "css" and no closing fence, capture from the opening fence to end:
    if block_type == "css":
        start_pattern = r"```css\s*(.*)$"
        match2 = re.search(start_pattern, text, re.DOTALL)
        if match2:
            content = match2.group(1).strip()
            print(f"[DEBUG] CSS fence never closed—captured truncated CSS (length {len(content)})")
            return content

    print(f"[DEBUG] Failed to extract {block_type} block.")
    return ""


async def main(url: str) -> None:
    print(f"[DEBUG] Scraping {url}…\n")

    # 1) Run our existing scraper (visits with Browserbase + Playwright, extracts summary, full HTML, full CSS)
    context = await scrape_website(url)
    context_dict = context.model_dump()  # Pydantic V2 method
    
    # 2) Save the raw context to context.json
    CONTEXT_FILE.write_text(json.dumps(context_dict, indent=2, default=str))
    print("[DEBUG] context.json written.\n")

    # 3) Grab the full HTML and raw CSS (for filtering)
    full_html = context_dict.get("html", "")
    raw_css = context_dict.get("css_contents", "")
    print(f"[DEBUG] raw_html length: {len(full_html)} chars")
    print(f"[DEBUG] raw_css length: {len(raw_css)} chars\n")

    # 4) Filter CSS once (only rules matching any selector in the HTML)
    filtered_css = filter_css_from_html_and_css(full_html, raw_css)
    print(f"[DEBUG] filtered_css length: {len(filtered_css)} chars\n")

    # 5) Build a tiny “critical CSS” by further subsetting filtered_css
    critical_css = build_critical_css(filtered_css)
    print(f"[DEBUG] critical_css length: {len(critical_css)} chars\n")

    # 6) Build a summary JSON + minimal HTML snippet
    summary_json_obj, minimal_html = build_summary_and_minimal_html(context_dict)
    print(f"[DEBUG] summary keys: {list(summary_json_obj.keys())}")
    print(f"[DEBUG] minimal_html length: {len(minimal_html)} chars\n")

    # 7) Build the final prompt
    prompt = format_prompt(minimal_html, summary_json_obj, critical_css)
    print(f"[DEBUG] Prompt length: {len(prompt)} chars\n")

    # 8) Send prompt to Claude
    print("[DEBUG] Sending prompt to Claude…")
    client = anthropic.Anthropic(api_key=API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096  # increase if necessary
    )

    # 9) Collect and print raw Claude output
    text_content = "".join(part.text for part in response.content if hasattr(part, "text"))
    print("\n[RAW CLAUDE OUTPUT]\n")
    print(text_content)
    print("\n[END RAW]\n")
    print(f"[DEBUG] Claude response length: {len(text_content)} chars\n")

    # 10) Extract HTML and CSS blocks (with truncated‐CSS fallback)
    html_result = extract_code("html", text_content)
    css_result = extract_code("css", text_content)

    # 11) Write to output files
    Path("recreated_page.html").write_text(html_result)
    Path("styles.css").write_text(css_result)
    print("✅ Done. Files written: recreated_page.html, styles.css\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
