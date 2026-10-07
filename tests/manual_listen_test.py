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
                return

            await gemini_page.bring_to_front()
            
            # Listen to network requests
            def handle_request(request):
                # Print interesting requests that might be audio/tts
                if "tts" in request.url.lower() or "audio" in request.url.lower() or "speech" in request.url.lower():
                    print(f"TTS NETWORK REQUEST: {request.url}")

            gemini_page.on("request", handle_request)
            
            print("Looking for a 'Listen' button to click manually...")
            clicked = await gemini_page.evaluate('''() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const listenBtn = buttons.find(b => {
                    const label = (b.getAttribute('aria-label') || '').toLowerCase();
                    return label.includes('listen') || label.includes('read aloud');
                });
                if (listenBtn) {
                    listenBtn.click();
                    return true;
                }
                return false;
            }''')

            if clicked:
                print("Clicked Listen button! Waiting 5 seconds to capture network traffic...")
                await gemini_page.wait_for_timeout(5000)
            else:
                print("No Listen button found.")
                
            await browser.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
