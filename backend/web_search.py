import urllib.parse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

SEARCH_TIMEOUT_MS = 20000
MAX_RESULTS = 5

async def search_web(query: str) -> list[dict]:
    """
    Searches DuckDuckGo HTML version using Playwright.
    Returns a list of dicts: [{"title": str, "url": str}, ...]
    """
    playwright = None
    browser = None
    results = []
    
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Build DuckDuckGo HTML URL
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        # Navigate
        await page.goto(search_url, timeout=SEARCH_TIMEOUT_MS, wait_until="domcontentloaded")
        
        # Wait a moment for results to be available
        try:
            await page.wait_for_selector(".result__a", timeout=5000)
        except PlaywrightTimeoutError:
            return [] # No results found or timeout waiting for elements

        # Extract links
        elements = await page.locator(".result__a").all()
        
        seen_urls = set()
        
        for el in elements:
            if len(results) >= MAX_RESULTS:
                break
                
            href = await el.get_attribute("href")
            title = await el.inner_text()
            
            if href and title:
                # Sometimes DDG uses redirect links, but usually in html version it's direct or starts with //duckduckgo
                # Actually html version has href="//duckduckgo.com/l/?uddg=..." for external links.
                # Let's decode if it's a redirect, otherwise use direct.
                final_url = href
                if "uddg=" in href:
                    try:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs:
                            final_url = qs["uddg"][0]
                    except:
                        pass
                
                # Filter out DDG internal links and obvious non-content pages
                if final_url.startswith("http") and final_url not in seen_urls:
                    seen_urls.add(final_url)
                    results.append({
                        "title": title.strip(),
                        "url": final_url
                    })

        return results

    except Exception as e:
        print(f"Web search failed: {e}")
        return []
        
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
