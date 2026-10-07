import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def run():
    print("Connecting to Chrome over CDP on port 9222...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            context = contexts[0] if contexts else None
            if not context:
                return

            gemini_page = None
            for page in context.pages:
                if "gemini.google.com" in page.url:
                    gemini_page = page
                    break
            
            if not gemini_page:
                gemini_page = await context.new_page()
                await gemini_page.goto("https://gemini.google.com/app")
            else:
                await gemini_page.bring_to_front()

            await context.add_init_script("""
                window.__LISTEN_CLICKED__ = false;
                document.addEventListener('click', (e) => {
                    const button = e.target.closest('button');
                    if (button) {
                        const label = (button.getAttribute('aria-label') || '').toLowerCase();
                        if (label.includes('listen') || label.includes('read aloud')) {
                            window.__LISTEN_CLICKED__ = true;
                            console.log("INTERCEPTED: Listen button was clicked automatically!");
                        }
                    }
                }, true);
            """)

            print("Reloading Gemini page to inject interceptors and latest content.js...")
            await gemini_page.reload()

            # CAPTURE ALL LOGS to catch errors
            gemini_page.on("console", lambda msg: print(f"PAGE LOG: {msg.type} - {msg.text}"))
            gemini_page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

            print("Waiting for page to load...")
            composer_selector = 'rich-textarea, textarea, [contenteditable="true"]'
            await gemini_page.wait_for_selector(composer_selector, state="visible", timeout=15000)
            await gemini_page.wait_for_timeout(2000)

            print("Typing prompt...")
            await gemini_page.click(composer_selector)
            await gemini_page.wait_for_timeout(500)
            await gemini_page.keyboard.type("Say exactly 'Test 1.4.0 logs' and nothing else.")
            await gemini_page.wait_for_timeout(500)
            
            print("Clicking Send button...")
            send_btn = await gemini_page.query_selector('button[aria-label="Send message"], button[aria-label="Send"]')
            if send_btn:
                await send_btn.click()
            else:
                await gemini_page.keyboard.press("Enter")

            print("Waiting for response to start generating...")
            await gemini_page.wait_for_timeout(3000)
            
            print("Monitoring for automatic click for up to 30 seconds...")
            click_detected = False
            for i in range(30):
                detected = await gemini_page.evaluate("window.__LISTEN_CLICKED__")

                if detected:
                    print("✅ CONFIRMED: The extension automatically clicked the Listen button!")
                    click_detected = True
                    break
                
                await gemini_page.wait_for_timeout(1000)

            if not click_detected:
                print("❌ FAILED: The listen button was never clicked.")
                
            await browser.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
