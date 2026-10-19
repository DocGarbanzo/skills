"""Print an artifact page to A4 PDF with headless Chromium and rasterise the pages for inspection.

    uv run --project <repo> --group print python print_check.py page.html [outdir]

Needs the `print` dependency group (playwright) and a Chromium: `uv run --group print playwright install chromium`
(or an existing Chromium via the env var CHROMIUM_PATH). Prints the page count and writes page-N.png files.
"""
import asyncio
import os
import subprocess
import sys


async def _pdf(html_path, pdf_path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        b = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        html = open(html_path, encoding="utf-8").read()
        await pg.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>' + html + "</body></html>")
        await pg.wait_for_timeout(500)
        await pg.emulate_media(media="print")
        await pg.pdf(path=pdf_path, format="A4", prefer_css_page_size=True, print_background=True)
        await b.close()
        return errors


def main(html_path, outdir="print_check"):
    os.makedirs(outdir, exist_ok=True)
    pdf = os.path.join(outdir, "print.pdf")
    errors = asyncio.run(_pdf(html_path, pdf))
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    pages = int(info.split("Pages:")[1].split()[0]) if "Pages:" in info else None
    subprocess.run(["pdftoppm", "-r", "50", "-png", pdf, os.path.join(outdir, "page")], check=False)
    print(f"{pages} A4 pages -> {outdir}/page-*.png" + (f"; JS errors: {errors}" if errors else ""))
    return pages


if __name__ == "__main__":
    main(*sys.argv[1:])
