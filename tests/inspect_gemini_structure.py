"""
Quick inspector: loads gemini.google.com in a fresh Chromium (no login needed)
to snapshot the pre-auth page structure, then opens Chrome with your profile
so you can manually send a message and watch console logs from the extension.
"""
import asyncio
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

EXTENSION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHROME_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
SNIPPET_PATH = os.path.join(os.path.dirname(__file__), "gemini_devtools_snippet.js")

WATCH_JS = """
// Injected by debug_test.py - patches content.js internals via console interception
// to show what the extension is doing in real time.
// This runs in the page context.
(function() {
  const orig = console.log.bind(console);

  // Observe for listen buttons every second and log what's found
  let tick = 0;
  const LISTEN_LABEL_PATTERN =
    /\\b(listen|listen to|read aloud|read response aloud|play response|speaker|volume_up|record_voice_over|text_to_speech)\\b/i;
  const EXCLUDED_LABEL_PATTERN =
    /\\b(stop|pause|resume|mute|unmute|microphone|mic|voice settings|settings)\\b/i;
  const normalizeText = (v) => v.replace(/\\s+/g, ' ').trim();
  const getLabel = (el) => normalizeText([
    el.getAttribute('aria-label') || '',
    el.getAttribute('title') || '',
    el.getAttribute('data-tooltip') || '',
    el.innerText || '',
  ].join(' '));
  const isVisible = (el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };

  const interval = setInterval(() => {
    tick++;
    const buttons = [...document.querySelectorAll('button, [role="button"]')];
    const listenBtns = buttons.filter(b => {
      const label = getLabel(b);
      return LISTEN_LABEL_PATTERN.test(label) && !EXCLUDED_LABEL_PATTERN.test(label) && isVisible(b);
    });
    if (listenBtns.length || tick % 5 === 0) {
      console.log(`[WATCHER tick=${tick}] total buttons: ${buttons.length}, listen buttons: ${listenBtns.length}`);
      for (const b of listenBtns) {
        console.log('  LISTEN BUTTON:', getLabel(b).slice(0, 80), b.outerHTML.slice(0, 200));
      }
    }
  }, 1000);

  setTimeout(() => clearInterval(interval), 120000);
  console.log('[WATCHER] installed - watching for listen buttons...');
})();
"""

async def inspect_fresh_chromium():
    """Load Gemini in a fresh Chromium to snapshot pre-auth page structure."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        console_msgs = []
        page.on("console", lambda m: console_msgs.append(m.text))

        print("Loading gemini.google.com in fresh Chromium (no profile)...")
        try:
            await page.goto("https://gemini.google.com", timeout=20000, wait_until="networkidle")
        except Exception as e:
            print(f"Navigation/timeout: {e}")

        await asyncio.sleep(3)
        title = await page.title()
        print(f"Page title: {title}")
        print(f"URL: {page.url}")

        # Check what button labels exist on the landing page
        labels = await page.evaluate("""() => {
          return [...document.querySelectorAll('button, [role="button"]')]
            .map(b => ({
              tag: b.tagName,
              ariaLabel: b.getAttribute('aria-label'),
              title: b.getAttribute('title'),
              tooltip: b.getAttribute('data-tooltip') || b.getAttribute('data-tooltip-text'),
              text: (b.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 50),
            }))
            .filter(b => b.ariaLabel || b.title || b.tooltip || b.text);
        }""")

        print(f"\nButtons on page ({len(labels)} with labels):")
        seen = set()
        for b in labels:
            key = (b['ariaLabel'], b['title'], b['tooltip'])
            if key in seen:
                continue
            seen.add(key)
            print(f"  [{b['tag']}] aria-label={b['ariaLabel']!r}  title={b['title']!r}  tooltip={b['tooltip']!r}  text={b['text']!r}")

        # Check if composer is detectable
        composers = await page.evaluate("""() => {
          return [...document.querySelectorAll('textarea, [contenteditable="true"]')]
            .map(el => ({
              tag: el.tagName,
              contenteditable: el.getAttribute('contenteditable'),
              ariaLabel: el.getAttribute('aria-label'),
              placeholder: el.getAttribute('placeholder'),
            }));
        }""")
        print(f"\nComposer/textarea elements ({len(composers)}):")
        for c in composers:
            print(f"  [{c['tag']}] contenteditable={c['contenteditable']!r} aria-label={c['ariaLabel']!r} placeholder={c['placeholder']!r}")

        await asyncio.sleep(3)
        await browser.close()


async def open_gemini_with_extension():
    """
    Try to open Chrome with the extension loaded using a COPY of the profile
    (avoids conflict with running Chrome).
    """
    import shutil
    import tempfile

    profile_src = os.path.join(CHROME_PROFILE, "Default")
    if not os.path.isdir(profile_src):
        print("Chrome Default profile not found.")
        return

    tmp_dir = tempfile.mkdtemp(prefix="gemini_debug_")
    tmp_profile = os.path.join(tmp_dir, "User Data")
    tmp_default = os.path.join(tmp_profile, "Default")
    os.makedirs(tmp_default, exist_ok=True)

    # Copy only the essential auth files (Cookies + Local State) - fast and safe
    print(f"Copying Chrome auth cookies to temp profile at {tmp_dir} ...")
    for fname in ["Cookies", "Login Data", "Web Data"]:
        src = os.path.join(profile_src, fname)
        if fname == "Cookies" and not os.path.isfile(src):
            net_src = os.path.join(profile_src, "Network", "Cookies")
            if os.path.isfile(net_src):
                os.makedirs(os.path.join(tmp_default, "Network"), exist_ok=True)
                try:
                    shutil.copy2(net_src, os.path.join(tmp_default, "Network", "Cookies"))
                    print("  Copied Network/Cookies")
                    continue
                except Exception as e:
                    print(f"  Could not copy Network/Cookies: {e}")
                    continue
        if os.path.isfile(src):
            try:
                shutil.copy2(src, tmp_default)
                print(f"  Copied {fname}")
            except Exception as e:
                print(f"  Could not copy {fname}: {e}")

    state_src = os.path.join(CHROME_PROFILE, "Local State")
    if os.path.isfile(state_src):
        try:
            shutil.copy2(state_src, tmp_profile)
            print("  Copied Local State")
        except Exception as e:
            print(f"  Could not copy Local State: {e}")

    async with async_playwright() as p:
        print("\nLaunching Chromium with extension and temp profile...")
        try:
            context = await p.chromium.launch_persistent_context(
                tmp_profile,
                channel="chrome",
                headless=False,
                slow_mo=0,
                args=[
                    f"--load-extension={EXTENSION_DIR}",
                    f"--disable-extensions-except={EXTENSION_DIR}",
                    "--no-first-run",
                ],
            )
        except Exception as e:
            print(f"Failed to launch: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        page = context.pages[0] if context.pages else await context.new_page()

        console_msgs = []
        def on_console(msg):
            txt = f"[{msg.type.upper()}] {msg.text}"
            console_msgs.append(txt)
            if "[DBG]" in txt or "[WATCHER]" in txt or "LISTEN" in txt.upper() or "arm" in txt.lower():
                print("  CONSOLE:", txt)

        page.on("console", on_console)

        print("Navigating to Gemini...")
        try:
            await page.goto("https://gemini.google.com", timeout=30000)
        except Exception as e:
            print(f"Navigation error: {e}")

        await asyncio.sleep(3)

        # Inject the watcher
        try:
            await page.evaluate(WATCH_JS)
            print("Watcher injected. Send a message in Gemini and watch the console output here.")
        except Exception as e:
            print(f"Could not inject watcher: {e}")

        # Read the devtools snippet and show it
        with open(SNIPPET_PATH, encoding="utf-8") as f:
            snippet = f.read()

        print("\n" + "="*60)
        print("MANUAL STEP: After the Gemini response finishes, open DevTools")
        print("(F12) and paste tests/gemini_devtools_snippet.js in the Console.")
        print("="*60)
        print("\nKeeping browser open for 90 seconds to let you test manually...")
        print("Watch above for CONSOLE: lines from the watcher.\n")

        for i in range(90):
            await asyncio.sleep(1)
            if i % 10 == 9:
                print(f"  {i+1}s elapsed...")

        await context.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="Only inspect fresh Chromium (no profile)")
    parser.add_argument("--live", action="store_true", help="Open Gemini with extension loaded (copies profile)")
    args = parser.parse_args()

    if args.fresh or not args.live:
        asyncio.run(inspect_fresh_chromium())
    if args.live or not args.fresh:
        asyncio.run(open_gemini_with_extension())
