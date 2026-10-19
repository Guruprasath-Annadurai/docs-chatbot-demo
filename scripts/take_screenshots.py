"""Takes the README screenshots from a running server.

    uvicorn app.main:create_app --factory --port 8000   # in one terminal
    python scripts/take_screenshots.py                  # in another

Needs: pip install playwright && playwright install chromium
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def ask(page, question: str) -> None:
    count = page.locator(".msg.user").count()
    page.fill("#question", question)
    page.click("#send")
    page.wait_for_function(
        "n => document.querySelectorAll('.msg.user').length > n && document.querySelector('#log .msg:last-child .bubble').textContent !== '…'",
        arg=count,
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 820}, device_scale_factor=1)

    page.goto(BASE)
    page.wait_for_selector("#docs li")
    ask(page, "What time do you open on Sunday?")
    page.screenshot(path=OUT / "answer-with-sources.png")

    page.goto(BASE)
    page.wait_for_selector("#docs li")
    ask(page, "Do you repair laptops?")
    page.click("text=Talk to a human")
    page.fill("form.human input[name=name]", "Asha")
    page.fill("form.human input[name=email]", "asha@example.com")
    page.screenshot(path=OUT / "i-dont-know.png")

    page.goto(f"{BASE}/widget-demo")
    page.click("#docs-chatbot-widget >> .fab")
    page.fill("#docs-chatbot-widget >> form.ask input", "How much does a croissant cost?")
    page.click("#docs-chatbot-widget >> button.send")
    page.wait_for_selector("#docs-chatbot-widget >> .src")
    page.screenshot(path=OUT / "widget-demo.png")

    browser.close()
print("Saved screenshots to", OUT)
