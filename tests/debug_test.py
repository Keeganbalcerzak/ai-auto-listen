"""
Debug script for Gemini Auto Listen extension.
Phase 1: smoke.html logic test (no auth needed)
Phase 2: live Gemini DOM inspector (uses your Chrome profile - close Chrome first)
"""
import asyncio
import pathlib
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

SMOKE_HTML = pathlib.Path(__file__).parent / "smoke.html"
EXTENSION_DIR = pathlib.Path(__file__).parent.parent
CHROME_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")

# Patterns from content.js (mirrored exactly)
LISTEN_PATTERN = r"(?i)\b(listen|listen to|read aloud|read response aloud|play response|speaker|volume_up|record_voice_over|text_to_speech)\b"
EXCLUDED_PATTERN = r"(?i)\b(stop|pause|resume|mute|unmute|microphone|mic|voice settings|settings)\b"

GEMINI_INSPECTOR_JS = """() => {
  const LISTEN_LABEL_PATTERN =
    /\\b(listen|listen to|read aloud|read response aloud|play response|speaker|volume_up|record_voice_over|text_to_speech)\\b/i;
  const EXCLUDED_LABEL_PATTERN =
    /\\b(stop|pause|resume|mute|unmute|microphone|mic|voice settings|settings)\\b/i;
  const PROMPT_SUBMIT_LABEL_PATTERN =
    /\\b(send|send message|submit|regenerate|retry|try again)\\b/i;

  const normalizeText = (v) => v.replace(/\\s+/g, ' ').trim();

  const getLabel = (el) => {
    const parts = [
      el.getAttribute('aria-label') || '',
      el.getAttribute('title') || '',
      el.getAttribute('data-tooltip') || '',
      el.getAttribute('data-tooltip-text') || '',
      el.getAttribute('data-test-tooltip') || '',
      el.innerText || el.textContent || '',
    ];
    return normalizeText(parts.join(' '));
  };

  const isVisible = (el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };

  const allButtons = [...document.querySelectorAll('button, [role="button"]')];

  const results = {
    total_buttons: allButtons.length,
    listen_buttons: [],
    submit_buttons: [],
    response_roots_found: [],
  };

  for (const btn of allButtons) {
    const label = getLabel(btn);
    const vis = isVisible(btn);
    const isListen = LISTEN_LABEL_PATTERN.test(label) && !EXCLUDED_LABEL_PATTERN.test(label);
    const isSubmit = PROMPT_SUBMIT_LABEL_PATTERN.test(label) && !LISTEN_LABEL_PATTERN.test(label) && !EXCLUDED_LABEL_PATTERN.test(label);

    if (isListen || isSubmit || label.toLowerCase().includes('listen') || label.toLowerCase().includes('read') || label.toLowerCase().includes('speaker')) {
      const entry = {
        tag: btn.tagName,
        id: btn.id || null,
        class: btn.className.slice(0, 80),
        ariaLabel: btn.getAttribute('aria-label'),
        title: btn.getAttribute('title'),
        dataTooltip: btn.getAttribute('data-tooltip'),
        text: (btn.innerText || '').trim().slice(0, 60),
        label_computed: label.slice(0, 120),
        visible: vis,
        disabled: btn.disabled,
        isListen,
        isSubmit,
      };
      if (isListen) results.listen_buttons.push(entry);
      else if (isSubmit) results.submit_buttons.push(entry);
    }
  }

  // Check response root selectors
  const RESPONSE_ROOT_SELECTOR = [
    '[data-message-author-role="model"]',
    '[data-message-author-role="assistant"]',
    '[data-response-index]',
    '[data-testid*="response" i]',
    '[class*="model-response" i]',
    '[class*="response-container" i]',
    '[class*="response" i]',
    'message-content',
    'bard-response'
  ];
  for (const sel of RESPONSE_ROOT_SELECTOR) {
    const els = document.querySelectorAll(sel);
    if (els.length) {
      results.response_roots_found.push({ selector: sel, count: els.length });
    }
  }

  // Also check what composer/textarea is present
  results.composer_elements = [...document.querySelectorAll('textarea, [contenteditable="true"]')]
    .map(el => ({
      tag: el.tagName,
      id: el.id || null,
      placeholder: el.getAttribute('placeholder'),
      ariaLabel: el.getAttribute('aria-label'),
      visible: isVisible(el),
    }));

  return results;
}"""


async def run_smoke_test(playwright):
    print("\n" + "="*60)
    print("PHASE 1: Smoke test (tests/smoke.html)")
    print("="*60)

    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append(f"[{msg.type.upper()}] {msg.text}"))
    page.on("pageerror", lambda err: console_msgs.append(f"[PAGEERROR] {err}"))

    url = SMOKE_HTML.as_uri()
    print(f"Loading: {url}")
    await page.goto(url)

    print("Waiting 7s for smoke sequence to complete...")
    await asyncio.sleep(7)

    new_clicked = await page.evaluate("document.body.dataset.newClicked")
    old_clicked = await page.evaluate("document.body.dataset.oldClicked")

    print(f"\n  new-listen clicked: {new_clicked!r}  (want 'true')")
    print(f"  old-listen clicked: {old_clicked!r}   (want None/falsy)")

    if new_clicked == "true":
        print("\n  PASS - smoke test logic works correctly.")
        print("  The bug is on the real Gemini page, not in the core logic.")
    else:
        print("\n  FAIL - there is a logic bug in content.js!")
        print("  Console output:")
        for msg in console_msgs:
            print("   ", msg)

    await browser.close()
    return new_clicked == "true"


async def run_gemini_inspector(playwright):
    print("\n" + "="*60)
    print("PHASE 2: Live Gemini DOM inspector")
    print("="*60)

    profile_path = CHROME_PROFILE
    if not os.path.isdir(profile_path):
        print(f"  Chrome profile not found at: {profile_path}")
        print("  Skipping live Gemini inspection.")
        return

    print(f"  Using Chrome profile: {profile_path}")
    print("  NOTE: Chrome must be fully closed before running this.")
    print("  Navigating to gemini.google.com ...\n")

    try:
        context = await playwright.chromium.launch_persistent_context(
            profile_path,
            channel="chrome",
            headless=False,
            args=[
                f"--load-extension={EXTENSION_DIR}",
                "--disable-extensions-except=" + str(EXTENSION_DIR),
            ],
        )
    except Exception as e:
        print(f"  Could not launch with Chrome profile: {e}")
        print("  If Chrome is running, close it and try again.")
        return

    page = context.pages[0] if context.pages else await context.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append(f"[{msg.type.upper()}] {msg.text}"))

    try:
        await page.goto("https://gemini.google.com", timeout=30000)
    except Exception as e:
        print(f"  Navigation failed: {e}")
        await context.close()
        return

    print("  Page loaded. Waiting 4s for page to fully render...")
    await asyncio.sleep(4)

    title = await page.title()
    url = page.url
    print(f"  Title: {title}")
    print(f"  URL:   {url}")

    print("\n  Inspecting DOM for buttons and response areas...")
    try:
        info = await page.evaluate(GEMINI_INSPECTOR_JS)
    except Exception as e:
        print(f"  JS evaluation failed: {e}")
        await context.close()
        return

    print(f"\n  Total buttons/role=button on page: {info['total_buttons']}")

    print("\n  --- Listen buttons found (would be auto-clicked) ---")
    if info["listen_buttons"]:
        for b in info["listen_buttons"]:
            print(f"    [{b['tag']}] aria-label={b['ariaLabel']!r} title={b['title']!r} "
                  f"tooltip={b['dataTooltip']!r} text={b['text']!r} visible={b['visible']}")
    else:
        print("    NONE FOUND - extension cannot find the listen button!")
        print("    This is likely the root cause.")

    print("\n  --- Submit/Send buttons found ---")
    if info["submit_buttons"]:
        for b in info["submit_buttons"]:
            print(f"    [{b['tag']}] aria-label={b['ariaLabel']!r} title={b['title']!r} text={b['text']!r} visible={b['visible']}")
    else:
        print("    None found matching submit patterns")

    print("\n  --- Response root selectors matched ---")
    if info["response_roots_found"]:
        for r in info["response_roots_found"]:
            print(f"    {r['selector']!r}: {r['count']} element(s)")
    else:
        print("    NONE - response container selectors do not match Gemini's DOM!")

    print("\n  --- Composer/textarea elements ---")
    for c in info.get("composer_elements", []):
        print(f"    [{c['tag']}] id={c['id']!r} placeholder={c['placeholder']!r} "
              f"aria-label={c['ariaLabel']!r} visible={c['visible']}")

    # Dump all button labels to help identify the real listen button
    print("\n  --- ALL button labels on page (to find the real listen button) ---")
    all_labels = await page.evaluate("""() => {
      return [...document.querySelectorAll('button, [role="button"]')]
        .map(b => ({
          ariaLabel: b.getAttribute('aria-label'),
          title: b.getAttribute('title'),
          tooltip: b.getAttribute('data-tooltip') || b.getAttribute('data-tooltip-text'),
          text: (b.innerText || '').trim().slice(0, 40),
        }))
        .filter(b => b.ariaLabel || b.title || b.tooltip || b.text)
        .slice(0, 60);
    }""")
    seen = set()
    for b in all_labels:
        key = (b['ariaLabel'], b['title'], b['tooltip'])
        if key in seen:
            continue
        seen.add(key)
        print(f"    aria-label={b['ariaLabel']!r}  title={b['title']!r}  "
              f"tooltip={b['tooltip']!r}  text={b['text']!r}")

    print("\n  Keeping browser open for 10s so you can inspect manually...")
    await asyncio.sleep(10)
    await context.close()


async def main():
    async with async_playwright() as p:
        smoke_ok = await run_smoke_test(p)

        if smoke_ok:
            await run_gemini_inspector(p)
        else:
            print("\nFix the smoke test logic bug before inspecting the live page.")

if __name__ == "__main__":
    asyncio.run(main())
