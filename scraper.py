"""
Ekantipur.com Scraper
Extracts top 5 entertainment news articles and the Cartoon of the Day.
Uses Playwright with Python for browser automation.
"""

import json
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def safe_text(element, selector=None):
    try:
        if selector:
            child = element.query_selector(selector)
            return child.text_content().strip() if child else None
        return element.text_content().strip()
    except Exception:
        return None


def safe_attr(element, selector=None, attr="src"):
    try:
        target = element.query_selector(selector) if selector else element
        val = target.get_attribute(attr) if target else None
        return val.strip() if val else None
    except Exception:
        return None


def _console_text(s, max_len=60):
    if not s:
        return ""
    chunk = s[:max_len]
    return chunk.encode("utf-8", errors="replace").decode("utf-8")


def make_absolute_url(url, base="https://ekantipur.com"):
    if not url:
        return None
    if url.startswith("http"):
        return url
    return base + url if url.startswith("/") else base + "/" + url


def _card_image_url(card):
    """Lazy images: real URL in data-src; fallback to src."""
    try:
        img_el = card.query_selector("img.lazy") or card.query_selector("img")
        if not img_el:
            return None
        u = img_el.get_attribute("data-src") or img_el.get_attribute("src")
        return u.strip() if u else None
    except Exception:
        return None


def extract_entertainment_news(page):
    print("[*] Navigating to Entertainment section...")
    try:
        page.goto("https://ekantipur.com/entertainment", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError:
        print("[!] Timeout, continuing with what loaded...")

    try:
        page.wait_for_selector(".category-inner-wrapper a[href]", timeout=30000)
    except PlaywrightTimeoutError:
        print("[!] Timeout waiting for article links, continuing...")

    page.wait_for_timeout(2000)

    articles = []
    cards = page.query_selector_all(".category-inner-wrapper")

    for card in cards:
        title = (
            safe_text(card, ".category-description a") or
            safe_text(card, "h1") or
            safe_text(card, "h2") or
            safe_text(card, "h3") or
            safe_text(card, "h4") or
            safe_text(card, "h5") or
            safe_text(card, "[class*='title']") or
            safe_text(card, "[class*='headline']") or
            safe_text(card, "p")
        )

        img_raw = _card_image_url(card)
        img_url = make_absolute_url(img_raw)

        category = "मनोरञ्जन"

        author = None
        try:
            an_el = card.query_selector(".author-name span")
            if an_el:
                raw_au = an_el.text_content()
                author = raw_au.strip() if raw_au else None
        except Exception:
            pass
        if not author:
            author = (
                safe_text(card, "[class*='author']") or
                safe_text(card, "[class*='byline']") or
                safe_text(card, "[class*='reporter']")
            )

        articles.append({
            "title": title,
            "image_url": img_url,
            "category": category,
            "author": author,
        })

    articles = [
        a for a in articles
        if a.get("title") is not None
        and str(a["title"]).strip() != ""
        and a.get("image_url")
    ][:5]

    for i, a in enumerate(articles, start=1):
        print(f"  [+] Article {i}: {_console_text(a['title'])}")

    print(f"[*] Extracted {len(articles)} entertainment articles.")
    return articles


def extract_cartoon_of_the_day(page):
    print("[*] Looking for Cartoon of the Day...")
    try:
        page.goto("https://ekantipur.com/cartoon", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError:
        print("[!] Timeout on cartoon page, continuing...")

    page.evaluate("window.scrollBy(0, 300)")
    page.wait_for_timeout(1500)

    cartoon_el = (
        page.query_selector("[class*='cartoon']") or
        page.query_selector("[class*='caricature']") or
        page.query_selector("article") or
        page.query_selector(".story-detail") or
        page.query_selector(".detail-content") or
        page.query_selector("main")
    )

    if cartoon_el:
        title = (
            safe_text(cartoon_el, "h1") or
            safe_text(cartoon_el, "h2") or
            safe_text(cartoon_el, "[class*='title']") or
            "Cartoon of the Day"
        )
        img_url = (
            safe_attr(cartoon_el, "img", "src") or
            safe_attr(cartoon_el, "img", "data-src")
        )
        img_url = make_absolute_url(img_url)
        # Try all likely author selectors inside the cartoon card
        author = (
            safe_text(cartoon_el, ".cartoon-description .author-name") or
            safe_text(cartoon_el, ".cartoon-description span") or
            safe_text(cartoon_el, ".author-name") or
            safe_text(cartoon_el, ".date")  # sometimes author and date share a container
        )
        # Strip date-like patterns (digits, /, -) to isolate just the name
        if author:
            # Remove lines that look like dates e.g. "१२ मे २०२६"
            lines = [l.strip() for l in author.splitlines() if l.strip()]
            non_date = [l for l in lines if not re.search(r"\d", l)]
            author = non_date[0] if non_date else lines[0] if lines else None
        print(f"  [+] Cartoon: {_console_text(title)}")
        return {"title": title, "image_url": img_url, "author": author}

    return {"title": None, "image_url": None, "author": None}


def main():
    output = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        output["entertainment_news"] = extract_entertainment_news(page)
        output["cartoon_of_the_day"] = extract_cartoon_of_the_day(page)

        browser.close()

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n[OK] Data saved to output.json")
    print(f"    Entertainment articles: {len(output['entertainment_news'])}")
    print(f"    Cartoon: {'Found' if output['cartoon_of_the_day']['title'] else 'Not found'}")


if __name__ == "__main__":
    main()