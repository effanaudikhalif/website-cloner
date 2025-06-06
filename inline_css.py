from pathlib import Path

html_path = Path("recreated_page.html")
css_path = Path("styles.css")

# Read both files
html = html_path.read_text()
css = css_path.read_text()

# Replace <link> or insert <style> tag in the <head>
if "<head>" in html:
    inlined_html = html.replace("<head>", f"<head>\n<style>\n{css}\n</style>\n")
else:
    # fallback if <head> not found
    inlined_html = f"<style>\n{css}\n</style>\n" + html

# Save to a new file
output_path = Path("recreated_combined.html")
output_path.write_text(inlined_html)

print(f"✅ Combined file saved as {output_path}")
