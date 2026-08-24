import socket
import ipaddress
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

MAX_TEXT_LENGTH = 50000
NAVIGATION_TIMEOUT_MS = 30000

def is_valid_url(url: str) -> tuple[bool, str | None]:
    """
    Validates a URL:
    - Must be http or https
    - Hostname must resolve to a public IP (no local/private IPs)
    Returns (is_valid, error_message).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Only http and https URLs are supported."

        if not parsed.hostname:
            return False, "Invalid URL format."

        # Reject obvious local hostnames
        if parsed.hostname.lower() in ("localhost", "127.0.0.1", "::1"):
            return False, "Localhost URLs are not permitted."

        try:
            # Resolve the hostname to an IP address
            ip = socket.gethostbyname(parsed.hostname)
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                 return False, f"URL resolves to a private or reserved IP address ({ip})."
        except socket.gaierror:
            return False, "Could not resolve hostname."
        except ValueError:
            pass # Not a valid IP, maybe a weird hostname

        return True, None
    except Exception as e:
        return False, f"URL validation failed: {str(e)}"

async def scrape_page(url: str) -> dict:
    """
    Scrapes a webpage using Playwright.
    Returns:
        {
            "success": bool,
            "content": str | None,
            "error": str | None
        }
    """
    # 1. Validate the URL
    is_valid, error_msg = is_valid_url(url)
    if not is_valid:
        return {
            "success": False,
            "content": None,
            "error": error_msg
        }

    # 2. Run the Playwright scraping
    playwright = None
    browser = None
    try:
        playwright = await async_playwright().start()
        # Launch Chromium headless
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to the URL
        await page.goto(url, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
        
        # Extract visible text from the body
        text_content = await page.evaluate("() => document.body ? document.body.innerText : ''")
        
        if not text_content or not text_content.strip():
             return {
                 "success": False,
                 "content": None,
                 "error": "No visible text found on the page."
             }
             
        # Clean up the text: remove excessive blank lines and leading/trailing whitespace
        lines = [line.strip() for line in text_content.split('\n')]
        # Keep non-empty lines, preserving single newlines for structure
        cleaned_text = '\n'.join(line for line in lines if line)
        
        # Limit text length
        if len(cleaned_text) > MAX_TEXT_LENGTH:
            cleaned_text = cleaned_text[:MAX_TEXT_LENGTH] + "\n...[Content truncated]"
            
        return {
            "success": True,
            "content": cleaned_text,
            "error": None
        }

    except PlaywrightTimeoutError:
        return {
            "success": False,
            "content": None,
            "error": f"Navigation timeout exceeded ({NAVIGATION_TIMEOUT_MS}ms)."
        }
    except Exception as e:
        return {
            "success": False,
            "content": None,
            "error": f"Scraping failed: {str(e)}"
        }
    finally:
        # Ensure Playwright browser is closed even if errors occur
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
