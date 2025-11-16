import asyncio
import random
from playwright.async_api import async_playwright
import pandas as pd
import time


class CustomScraper:
    def __init__(self, base_url, headless=True):
        self.base_url = base_url
        self.headless = headless
        self.data = []

        # User agents make your bot look like a real browser to avoid blocking
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]

    async def run(self):
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)

            # Create a context with a random user agent
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            print(f"🕷️ Starting scrape on: {self.base_url}")

            try:
                await page.goto(self.base_url, timeout=60000)

                # === CUSTOMIZATION SECTION: WAIT FOR ELEMENT ===
                # Wait for the main items to load (Change '.product-item' to your target CSS selector)
                # await page.wait_for_selector('.product-item')

                # Optional: Scroll down to trigger lazy-loading images
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)  # Polite wait

                # === EXTRACTION LOGIC ===
                # This is where you define what to grab.
                # Example: Grabbing titles from a news site or products from a shop

                # 1. Select all containers (cards/rows)
                # Change 'article' to the specific tag or class of the item container
                items = await page.query_selector_all('article')

                print(f"Found {len(items)} items. Extracting...")

                for item in items:
                    # 2. Extract details from within each container
                    # These selectors (h2, a, .price) must be customized for your site
                    title_el = await item.query_selector('h2')
                    link_el = await item.query_selector('a')

                    # Safe extraction (handles missing data gracefully)
                    title = await title_el.inner_text() if title_el else "N/A"
                    link = await link_el.get_attribute('href') if link_el else "N/A"

                    self.data.append({
                        'Title': title,
                        'Link': link,
                        'Scraped_At': time.strftime("%Y-%m-%d %H:%M:%S")
                    })

            except Exception as e:
                print(f"❌ Error occurred: {e}")

            finally:
                # await browser.close()
                self.save_data()

    def save_data(self):
        if self.data:
            df = pd.DataFrame(self.data)
            filename = 'scraped_data.csv'
            df.to_csv(filename, index=False)
            print(f"✅ Success! Saved {len(self.data)} rows to {filename}")
        else:
            print("⚠️ No data found. Check your CSS selectors.")


# --- RUNNER ---
if __name__ == "__main__":
    # REPLACE THIS URL with the site you want to scrape
    target_url = "https://news.ycombinator.com/"

    # headless=False lets you watch it work
    scraper = CustomScraper(base_url=target_url, headless=False)
    asyncio.run(scraper.run())
