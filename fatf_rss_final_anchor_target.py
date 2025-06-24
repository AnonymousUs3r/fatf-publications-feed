import sys
import asyncio
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from playwright.async_api import async_playwright

async def main():
    url = "https://www.fatf-gafi.org/en/publications.html"
    filename = sys.argv[1] if len(sys.argv) > 1 else "fatf_feed_anchor.xml"

    print("🚀 Launching Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"🌐 Visiting: {url}")
        await page.goto(url, timeout=60000)

        try:
            selector = "div.cmp-faceted-search__search-bar form button[type='submit']"
            print("🔍 Waiting for correct search button...")
            await page.wait_for_selector(selector, state="attached", timeout=20000)

            locator = page.locator(selector)
            await locator.scroll_into_view_if_needed()
            await page.wait_for_timeout(1000)

            print("🖱️ Clicking the search icon...")
            await locator.click()
            await page.wait_for_timeout(5000)

            print("⌛ Waiting for real results (h3 > a) to appear...")
            await page.wait_for_selector("div.cmp-search-results__result__content h3 a", state="attached", timeout=20000)

        except Exception as e:
            print(f"❌ Encountered an error: {e}")
            await browser.close()
            input("⏸ Press Enter to exit...")
            return

        print("✅ Page ready. Extracting HTML...")
        content = await page.content()
        await browser.close()

    print("🧪 Parsing results with BeautifulSoup...")
    soup = BeautifulSoup(content, "html.parser")
    anchors = soup.select("div.cmp-search-results__result__content h3 a")

    fg = FeedGenerator()
    fg.id(url)
    fg.title("FATF Latest Publications")
    fg.link(href=url, rel="alternate")
    fg.description("Recent reports and updates from the Financial Action Task Force (FATF)")
    fg.language("en")

    print(f"📦 Found {len(anchors)} entries")
    added = 0
    for a in anchors:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue

        full_link = "https://www.fatf-gafi.org" + href if href.startswith("/") else href
        pub_date = datetime.now(timezone.utc)  # fallback

        parent = a.find_parent("div", class_="cmp-search-results__result__content")
        desc = parent.select_one("span.cmp-search-result__description") if parent else None
        if desc:
            try:
                date_text = desc.get_text(strip=True)[:7]
                dt = datetime.strptime(date_text, "%B %Y")
                pub_date = dt.replace(day=1, tzinfo=timezone.utc)
            except:
                pass

        entry = fg.add_entry()
        entry.id(full_link)
        entry.guid(full_link, permalink=True)
        entry.title(title)
        entry.link(href=full_link)
        entry.pubDate(pub_date)
        added += 1
        print(f"  ➕ {title}")

    fg.rss_file(filename)
    print(f"✅ RSS written to {filename} with {added} entries")
    input("⏸ Done. Press Enter to close...")

if __name__ == "__main__":
    asyncio.run(main())
