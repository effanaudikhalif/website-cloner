# backend/inline_css.py

def inline_css(html: str, css: str) -> str:
    """
    Inserts the given CSS into the <head> section of the given HTML string.
    Returns the combined HTML as a string.
    """
    if "<head>" in html:
        inlined_html = html.replace(
            "<head>",
            f"<head>\n  <style>\n{css}\n  </style>\n"
        )
    else:
        # fallback: just prepend the CSS if no <head> tag
        inlined_html = f"<style>\n{css}\n</style>\n" + html

    return inlined_html
