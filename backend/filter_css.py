from bs4 import BeautifulSoup
import cssutils

def extract_used_selectors(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Extract tags like div, p, section, etc.
    tags = set(tag.name for tag in soup.find_all())

    # Extract class names like 'hero', 'cta-button', etc.
    classes = set(cls for tag in soup.find_all(class_=True) for cls in tag.get('class'))

    # Extract ids like 'main-header', etc.
    ids = set(tag['id'] for tag in soup.find_all(id=True))

    return tags, classes, ids

def filter_css(css, used_tags, used_classes, used_ids):
    css_parser = cssutils.CSSParser()
    stylesheet = css_parser.parseString(css)
    filtered_css = ""

    for rule in stylesheet.cssRules:
        if rule.type == rule.STYLE_RULE:
            selectors = rule.selectorText.split(',')
            kept_selectors = []

            for sel in selectors:
                sel = sel.strip()

                if sel.startswith('.'):
                    if sel[1:] in used_classes:
                        kept_selectors.append(sel)
                elif sel.startswith('#'):
                    if sel[1:] in used_ids:
                        kept_selectors.append(sel)
                else:
                    # Handle compound selectors like 'div.header', 'section.hero > h2'
                    base_sel = sel.split()[0].split(':')[0].split('.')[0].split('#')[0]
                    if base_sel in used_tags:
                        kept_selectors.append(sel)

            if kept_selectors:
                rule.selectorText = ', '.join(kept_selectors)
                filtered_css += rule.cssText + "\n"

    return filtered_css

if __name__ == "__main__":
    # Read your simplified HTML and full CSS
    with open("recreated_page.html", "r") as html_file:
        html = html_file.read()

    with open("style.css", "r") as css_file:
        css = css_file.read()

    used_tags, used_classes, used_ids = extract_used_selectors(html)
    cleaned_css = filter_css(css, used_tags, used_classes, used_ids)

    # Save the filtered CSS
    with open("filtered_style.css", "w") as out_file:
        out_file.write(cleaned_css)

    print("Filtered CSS written to filtered_style.css")
