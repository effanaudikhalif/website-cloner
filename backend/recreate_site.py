# backend/recreate_site.py

import json
import re
import sys
from pathlib import Path
import asyncio
import anthropic
import os
from dotenv import load_dotenv

from scraper import scrape_website
from filter_css import filter_css_from_html_and_css

# ── create (or ensure) a “generated” folder next to this script ──
GENERATED_DIR = Path(__file__).parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Where to dump the scraped context
CONTEXT_FILE = GENERATED_DIR / "context.json"

load_dotenv()


def build_summary_and_minimal_html(context: dict) -> (dict, str):
    summary = {}
    full_title = context.get("title", "")
    site_name = full_title.split("|")[-1].strip() or "Site"

    # 1) NAV LINKS
    nav_links = []
    for href in context.get("summary", {}).get("nav_links", [])[:5]:
        label = href.rstrip("/").split("/")[-1].replace("-", " ").title() or href
        nav_links.append({"href": href, "label": label})
    summary["nav_links"] = nav_links

    # 2) HERO – image, heading, subheading
    hero_img = context.get("images", [None])[0] or ""
    hero_heading = context.get("summary", {}).get("headings", [""])[0]
    paragraphs = context.get("summary", {}).get("paragraphs", [])
    hero_subheading = paragraphs[0] if paragraphs else ""

    # grab the first scraped button text, if any
    scraped_buttons = context.get("summary", {}).get("buttons", [])
    button_text = scraped_buttons[0] if scraped_buttons else None

    # include button only if we actually scraped one
    summary["hero"] = {
        "img": hero_img,
        "heading": hero_heading,
        "subheading": hero_subheading,
        "button_text": button_text  # may be None
    }

    # 3) NEWS CARDS
    cards = []
    for header in context.get("summary", {}).get("section_headers", [])[:3]:
        cards.append({"heading": header, "snippet": "Preview text..."})
    summary["news_cards"] = cards

    # 4) FOOTER LINKS
    footer_links = [{"label": l["label"], "href": l["href"]} for l in nav_links[:4]]
    summary["footer_links"] = footer_links

    # --- NEW: Add main_content_summaries to summary if present ---
    main_content_summaries = context.get("summary", {}).get("main_content_summaries", [])
    if main_content_summaries:
        summary["main_content_summaries"] = main_content_summaries

    # --- NEW: Add enhanced fields to summary if present ---
    for key in ["images_detailed", "buttons_detailed", "links_detailed", "testimonials"]:
        val = context.get("summary", {}).get(key, None)
        if val:
            summary[key] = val

    # Build the minimal HTML snippet
    parts = []
    # HEADER + NAV
    parts.append(f'<header class="site-header">')
    parts.append(f"  <h1>{full_title}</h1>")
    if nav_links:
        parts.append('  <nav class="main-nav"><ul>')
        for l in nav_links:
            parts.append(f'    <li><a href="{l["href"]}">{l["label"]}</a></li>')
        parts.append("  </ul></nav>")
    parts.append("</header>")

    # HERO
    parts.append('<section class="hero">')
    # Use first detailed hero image if available
    images_detailed = context.get("summary", {}).get("images_detailed", [])
    hero_img_src = images_detailed[0]["src"] if images_detailed else hero_img
    if hero_img_src:
        parts.append(f'  <img src="{hero_img_src}" alt="{hero_heading}">')
    parts.append('  <div class="hero-text">')
    parts.append(f"    <h2>{hero_heading}</h2>")
    parts.append(f"    <p>{hero_subheading}</p>")
    # Use styled buttons if available
    buttons_detailed = context.get("summary", {}).get("buttons_detailed", [])
    if buttons_detailed:
        for btn in buttons_detailed[:2]:
            btn_class = " ".join(btn["class"]) if btn["class"] else ""
            btn_style = f' style="{btn["style"]}"' if btn["style"] else ""
            parts.append(f'    <button class="{btn_class}"{btn_style}>{btn["text"]}</button>')
    elif button_text:
        parts.append(f"    <button>{button_text}</button>")
    parts.append("  </div>")
    parts.append("</section>")

    # TESTIMONIALS/CARDS
    testimonials = context.get("summary", {}).get("testimonials", [])
    if testimonials:
        parts.append('<section class="testimonials"><div class="testimonial-list">')
        for t in testimonials[:2]:
            parts.append('  <div class="testimonial-card">')
            if t.get("avatar"):
                parts.append(f'    <img src="{t["avatar"]}" alt="{t.get("author", "Avatar")}" class="testimonial-avatar">')
            parts.append(f'    <blockquote>{t["quote"]}</blockquote>')
            if t.get("author"):
                parts.append(f'    <div class="testimonial-author">{t["author"]}</div>')
            parts.append('  </div>')
        parts.append('</div></section>')

    # NEWS CARDS
    parts.append('<section class="news-cards"><div class="news-grid">')
    for c in cards:
        parts.append('  <article class="news-card">')
        parts.append(f"    <h3>{c['heading']}</h3>")
        parts.append(f"    <p>{c['snippet']}</p>")
        parts.append('    <a href="#" class="read-more">Read More</a>')
        parts.append("  </article>")
    parts.append("</div></section>")

    # FOOTER
    parts.append('<footer class="site-footer"><div class="footer-links"><ul>')
    for f in footer_links:
        parts.append(f'  <li><a href="{f["href"]}">{f["label"]}</a></li>')
    parts.append("</ul></div></footer>")

    minimal_html = "\n".join(parts)
    return summary, minimal_html


def build_critical_css(filtered_css: str) -> str:
    critical_selectors = [
        r"\bbody\b", r"\bh1\b", r"\bh2\b", r"\bh3\b", r"\ba\b", r"\bbutton\b",
        r"\.site-header\b", r"\.main-nav\b", r"\.hero\b", r"\.hero\s+img\b",
        r"\.hero-text\b", r"\.news-cards\b", r"\.news-grid\b",
        r"\.news-card\b", r"\.read-more\b", r"\.site-footer\b", r"\.footer-links\b"
    ]
    rules = re.findall(r"([^{]+\{[^}]*\})", filtered_css, re.DOTALL)
    critical = [
        rule.strip()
        for rule in rules
        if any(re.search(pat, rule.split("{", 1)[0]) for pat in critical_selectors)
    ]
    return "\n\n".join(critical).strip()


def format_prompt(min_html: str, summary: dict, critical_css: str) -> str:
    summary_json = json.dumps(summary, indent=2)
    return (
        "You are given a JSON summary, a minimal HTML snippet, and a small critical CSS snippet.\n"
        "Recreate a full, responsive, semantic HTML/CSS page that visually resembles the original "
        "website as closely as possible. Do not include any JavaScript or external CSS frameworks.\n\n"
        "❗️ Return exactly two fenced code blocks:\n"
        "   • One ```html``` containing the complete page markup\n"
        "   • One ```css``` containing the complete stylesheet\n\n"
        "Below is the JSON summary:\n"
        f"```json\n{summary_json}\n```\n\n"
        "Below is the minimal HTML snippet:\n"
        f"```html\n{min_html}\n```\n\n"
        "Below is the critical CSS snippet:\n"
        f"```css\n{critical_css}\n```\n\n"
        "✅ Requirements:\n"
        "- Use semantic tags (<header>,<nav>,<section>,<footer>).\n"
        "- Mobile-first responsive layout.\n"
        "- Follow provided colors, spacing, typography.\n"
        "- Use the provided images, buttons, and testimonials/cards as described in the JSON summary.\n"
        "- For each testimonial/card, include the avatar, quote, and author in a visually appealing card layout.\n"
        "- Style buttons according to their extracted classes and inline styles.\n"
        "- Place images in their appropriate sections as indicated by their parent context.\n"
    )


def extract_code(block_type: str, text: str) -> str:
    fence = rf"```{block_type}\s*(.*?)\s*```"
    match = re.search(fence, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if block_type == "css":
        fallback = re.search(r"```css\s*(.*)$", text, re.DOTALL)
        if fallback:
            return fallback.group(1).strip()
    return ""


async def main(url: str) -> None:
    print(f"[DEBUG] Scraping {url}…")
    ctx = await scrape_website(url)
    ctx_dict = ctx.model_dump()
    CONTEXT_FILE.write_text(json.dumps(ctx_dict, indent=2, default=str))

    filtered = filter_css_from_html_and_css(ctx_dict["html"], ctx_dict["css_contents"])
    critical = build_critical_css(filtered)
    summary, minimal_html = build_summary_and_minimal_html(ctx_dict)
    prompt = format_prompt(minimal_html, summary, critical)

    print("[DEBUG] Sending to Claude…")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    raw = "".join(p.text for p in resp.content if hasattr(p, "text"))

    html_out = extract_code("html", raw)
    css_out = extract_code("css", raw)

    (GENERATED_DIR / "recreated_page.html").write_text(html_out)
    (GENERATED_DIR / "styles.css").write_text(css_out)
    print("✅ Done. Files written to generated/")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
