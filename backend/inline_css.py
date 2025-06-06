# backend/inline_css.py

from pathlib import Path

# Point to the same “generated” folder that recreate_site.py uses
GENERATED_DIR = Path(__file__).parent / "generated"

# Paths under generated/
html_path = GENERATED_DIR / "recreated_page.html"
css_path = GENERATED_DIR / "styles.css"

# Make sure the generated folder exists
GENERATED_DIR.mkdir(exist_ok=True)

# Read both files
html = html_path.read_text()
css = css_path.read_text()

# Insert the CSS into a <style> tag right after <head>
if "<head>" in html:
    inlined_html = html.replace(
        "<head>",
        f"<head>\n  <style>\n{css}\n  </style>\n"
    )
else:
    # Fallback: prepend a <style> block if no <head> tag was found
    inlined_html = f"<style>\n{css}\n</style>\n" + html

# Write the combined output under generated/
output_path = GENERATED_DIR / "recreated_combined.html"
output_path.write_text(inlined_html)

print(f"✅ Combined file saved as {output_path.resolve()}")
