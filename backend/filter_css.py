# filter_css.py

import re
from bs4 import BeautifulSoup
from typing import Set


def extract_selectors_from_html(html: str) -> Set[str]:
    """Extract tag names, class selectors, and ID selectors used in the HTML."""
    soup = BeautifulSoup(html, "html.parser")

    tags = {tag.name for tag in soup.find_all()}
    classes = {f".{cls}" for tag in soup.find_all(class_=True) for cls in tag.get("class", [])}
    ids = {f"#{tag.get('id')}" for tag in soup.find_all(id=True)}

    return tags | classes | ids


def filter_css(css: str, used_selectors: Set[str]) -> str:
    """Keep only CSS rules that match used selectors."""
    filtered_rules = []

    # Pattern for CSS rules: selector { ... }
    rules = re.findall(r'([^{]+)\{[^}]*\}', css)

    for rule in rules:
        selectors = [s.strip() for s in rule.split(",")]
        if any(sel for sel in selectors if sel in used_selectors):
            full_rule = re.search(rf'({re.escape(rule)}\s*\{{[^}}]*\}})', css)
            if full_rule:
                filtered_rules.append(full_rule.group(1).strip())

    return "\n\n".join(filtered_rules)


def filter_css_from_html_and_css(html: str, css: str) -> str:
    """Entry point: given full HTML and CSS, return only used CSS rules."""
    used_selectors = extract_selectors_from_html(html)
    return filter_css(css, used_selectors)
