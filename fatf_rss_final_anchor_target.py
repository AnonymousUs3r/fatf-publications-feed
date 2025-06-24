import sys
import asyncio
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from playwright.async_api import async_playwright

async def main():
    url = "https://www.fatf-gafi.org/en/publications.html"
    filename = sys.argv[1] if len(sys.argv) > 1 else "fatf_feed_anchor.xml"

    print("🚀 Launching headless browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.tracing.start(screenshots=True, snapshots=True)

        page = await context.new_page()
        print(f"🌐 Visiting: {url}")
        await page.goto(url, timeout=60000)
        
        try:
            try:
                await page.click("button[title*='Accept']", timeout=5000)
                print("✅ Cookie banner dismissed")
            except:
                print("ℹ️ No cookie prompt appeared")

            print("⏳ Waiting for scripts to settle...")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(5000)  # Let JS hydrate

            container = "div.faceted-search.container"
            print(f"🔎 Waiting for container: {container}")
            await page.wait_for_selector(container, timeout=30000)

            search_button = "div.cmp-faceted-search__search-bar form button[type='submit']"
            print(f"🔍 Checking for search button: {search_button}")
            button_count = await page.locator(search_button).count()
            if button_count == 0:
                print("⚠️ Search button not found — page may not be rendering interactively in CI.")
                await context.tracing.stop(path="trace.zip")
                await browser.close()
                return

            locator = page.locator(search_button)
            await locator.scroll_into_view_if_needed()
            await page.wait_for_timeout(1000)
            await locator.click()
            await page.wait_for_timeout(5000)

            results_selector = "div.cmp-search-results__result__content h3 a"
            print(f"📄 Waiting for results: {results_selector}")
            await page.wait_for_selector(results_selector, timeout=30000)

        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            await context.tracing.stop(path="trace.zip")
            await browser.close()
            return

        print("✅ Results loaded. Parsing content...")
        content = await page.content()
        await context.tracing.stop(path="trace.zip")
        await browser.close()

    print("🧪 Parsing feed entries...")
    soup = BeautifulSoup(content, "html.parser")
    anchors = soup.select("div.cmp-search-results__result__content h3 a")

    fg = FeedGenerator()
    fg.id(url)
    fg.title("FATF Latest Publications")
    fg.link(href=url, rel="alternate")
    fg.description("Recent reports and updates from the Financial Action Task Force (FATF)")
    fg.language("en")

    print(f"📦 Found {len(anchors)} entries")
    for a in anchors:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue

        full_link = "https://www.fatf-gafi.org" + href if href.startswith("/") else href
        pub_date = datetime.now(timezone.utc)

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
        print(f"  ➕ {title}")

    fg.rss_file(filename)
    print(f"✅ RSS written to {filename}")

if __name__ == "__main__":
    asyncio.run(main())
