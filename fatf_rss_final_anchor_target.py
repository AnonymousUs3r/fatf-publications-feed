import sys
import asyncio
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from playwright.async_api import async_playwright

async def main():
    url = "https://www.fatf-gafi.org/en/publications.html"
    filename = sys.argv[1] if len(sys.argv) > 1 else "fatf_feed_anchor.xml"

    print("🚀 Launching headless Firefox browser...")
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        await context.tracing.start(screenshots=True, snapshots=True)

        page = await context.new_page()
        print(f"🌐 Navigating to: {url}")
        await page.goto(url, timeout=60000)

        try:
            try:
                await page.click("button[title*='Accept']", timeout=5000)
                print("✅ Cookie banner dismissed")
            except:
                print("ℹ️ No cookie prompt appeared")

            print("⏳ Waiting for full page hydration...")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(5000)

            print("🔍 Looking for container and search button...")
            await page.wait_for_selector("div.faceted-search.container", timeout=30000)

            selector = "div.cmp-faceted-search__search-bar form button[type='submit']"
            locator = page.locator(selector)
            await locator.scroll_into_view_if_needed()
            await page.wait_for_timeout(1000)
            await locator.click()
            await page.wait_for_timeout(5000)

            print("⌛ Waiting for results...")
            await page.wait_for_selector("div.cmp-search-results__result__content h3 a", timeout=30000)

        except Exception as e:
            print(f"❌ Scraping error: {e}")
            await context.tracing.stop(path="trace.zip")
            await browser.close()
            return

        content = await page.content()
        await context.tracing.stop(path="trace.zip")
        await browser.close()

    print("🧪 Parsing feed items...")
    soup = BeautifulSoup(content, "html.parser")
    items = soup.select("ul.cmp-search-results__list > li")

    fg = FeedGenerator()
    fg.id(url)
    fg.title("FATF Latest Publications")
    fg.link(href=url, rel="alternate")
    fg.description("Recent reports and updates from the Financial Action Task Force (FATF)")
    fg.language("en")

    for item in items:
        link = item.select_one("div.cmp-search-results__result__content h3 a")
        date_elem = item.select_one("p.cmp-search-results__result__date")

        if not link:
            continue

        title = link.get_text(strip=True)
        href = link.get("href", "")
        full_link = "https://www.fatf-gafi.org" + href if href.startswith("/") else href

        pub_date = None
        if date_elem:
            raw_date = date_elem.get_text(strip=True)
            clean_date = raw_date.replace("Publication date :", "").strip()
            try:
                dt = datetime.strptime(clean_date, "%d %b %Y")
                pub_date = dt.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"⚠️ Could not parse date from '{clean_date}': {e}")

        if pub_date is None:
            pub_date = datetime.now(timezone.utc)
            print(f"⚠️ Using fallback pubDate for '{title}'")

        print(f"📆 pubDate set for '{title}': {pub_date.isoformat()}")

        entry = fg.add_entry()
        entry.id(full_link)
        entry.guid(full_link, permalink=True)
        entry.title(title)
        entry.link(href=full_link)
        entry.pubDate(pub_date)
        entry.updated(pub_date)

    fg.rss_file(filename)
    print(f"✅ RSS feed written to {filename}")

if __name__ == "__main__":
    asyncio.run(main())
