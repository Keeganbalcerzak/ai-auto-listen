"""
Opens a fresh Chromium browser at gemini.google.com.
Log in manually, send a message, wait for a response.
This script watches the page and prints ALL button labels whenever they change.
Run: python tests\watch_gemini.py
"""
import asyncio
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright

LISTEN_LABEL_PATTERN_SRC = r"\b(listen|listen to|read aloud|read response aloud|play response|speaker|volume_up|record_voice_over|text_to_speech)\b"

WATCH_JS = """
(function() {
  let lastButtonSet = '';

  setInterval(() => {
    const buttons = [...document.querySelectorAll('button, [role="button"]')];

    const entries = buttons.map(b => {
      const parts = [
        b.getAttribute('aria-label'),
        b.getAttribute('title'),
        b.getAttribute('data-tooltip'),
        b.getAttribute('data-tooltip-text'),
        b.getAttribute('jsname'),
        (b.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40),
      ].filter(Boolean);
      const s = b.getComputedStyle ? null : null;
      const rect = b.getBoundingClientRect();
      const cs = window.getComputedStyle(b);
      const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && rect.width > 0;
      return parts.join('|') + (visible ? '' : '[HIDDEN]');
    });

    const key = entries.join(';;');
    if (key !== lastButtonSet) {
      lastButtonSet = key;
      console.log('BUTTONS_CHANGED:' + JSON.stringify(entries));
    }
  }, 500);

  console.log('WATCHER_READY');
})();
"""

async def main():
    async with async_playwright() as p:
        print("Opening Chromium browser...")
        print("-> Log in to Gemini, send a message, wait for the response to finish.")
        print("-> This terminal will print all button labels whenever they change.")
        print("-> Press Ctrl+C to stop.\n")

        browser = await p.chromium.launch(headless=False, slow_mo=0)
        context = await browser.new_context()
        page = await context.new_page()

        seen_sets = set()

        def on_console(msg):
            text = msg.text
            if text.startswith("BUTTONS_CHANGED:"):
                import json
                try:
                    entries = json.loads(text[len("BUTTONS_CHANGED:"):])
                except Exception:
                    return
                key = frozenset(entries)
                if key in seen_sets:
                    return
                seen_sets.add(key)

                print(f"\n--- Button set changed ({len(entries)} buttons) ---")
                for e in entries:
                    parts = e.replace('[HIDDEN]', '')
                    hidden = '[HIDDEN]' in e
                    # Highlight anything that might be the listen button
                    listen_keywords = ['listen', 'read aloud', 'speaker', 'volume', 'aloud', 'tts', 'audio']
                    is_interesting = any(kw in e.lower() for kw in listen_keywords)
                    marker = "  *** POSSIBLE LISTEN BUTTON ***" if is_interesting else ""
                    tag = "[hidden]" if hidden else "[visible]"
                    print(f"  {tag} {parts!r}{marker}")
            elif text == "WATCHER_READY":
                print("Watcher active — watching for button changes...")

        page.on("console", on_console)

        await page.goto("https://gemini.google.com", timeout=30000)
        await page.add_init_script(WATCH_JS)

        try:
            # Inject immediately too
            await page.evaluate(WATCH_JS)
        except Exception:
            pass

        print("Browser is open. Log in and send a Gemini prompt...")

        # Keep running until Ctrl+C
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nDone.")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
