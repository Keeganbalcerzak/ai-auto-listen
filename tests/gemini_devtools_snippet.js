// Paste this in DevTools console on gemini.google.com AFTER sending a message
// and waiting for the response to finish. It will show exactly what the
// extension sees and why it may or may not click the listen button.

(function diagnose() {
  const LISTEN_LABEL_PATTERN =
    /\b(listen|listen to|read aloud|read response|read response aloud|play response|play audio|speaker|volume_up|record_voice_over|text_to_speech|tts|aloud)\b/i;
  const EXCLUDED_LABEL_PATTERN =
    /\b(stop|pause|resume|mute|unmute|microphone|mic|voice settings|settings)\b/i;
  const LISTEN_ICON_NAMES = ['volume_up', 'record_voice_over', 'text_to_speech'];

  const normalizeText = (v) => v.replace(/\s+/g, ' ').trim();
  const getLabel = (el) => normalizeText([
    el.getAttribute('aria-label') || '',
    el.getAttribute('title') || '',
    el.getAttribute('data-tooltip') || '',
    el.getAttribute('data-tooltip-text') || '',
    el.getAttribute('data-test-tooltip') || '',
    el.innerText || el.textContent || '',
  ].join(' '));

  const hasListenIcon = (el) => {
    const matIconName = el.getAttribute('data-mat-icon-name') || el.getAttribute('fonticon') || '';
    if (LISTEN_ICON_NAMES.some(n => matIconName.includes(n))) return true;
    const iconEl = el.querySelector('mat-icon, [data-mat-icon-name], [fonticon]');
    if (iconEl) {
      const childName = iconEl.getAttribute('data-mat-icon-name') || iconEl.getAttribute('fonticon') || iconEl.textContent?.trim() || '';
      return LISTEN_ICON_NAMES.some(n => childName.includes(n));
    }
    return false;
  };

  const isVisible = (el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };

  const isEffectivelyVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    for (let node = el; node instanceof Element; node = node.parentElement) {
      const s = getComputedStyle(node);
      if (s.display === 'none' || s.visibility === 'hidden') return false;
    }
    return true;
  };

  const getHidingAncestors = (el) => {
    const hiding = [];
    for (let node = el; node instanceof Element && node !== document.body; node = node.parentElement) {
      const s = getComputedStyle(node);
      if (s.opacity === '0' || s.pointerEvents === 'none') {
        hiding.push({
          element: node,
          tag: node.tagName,
          class: node.className?.slice?.(0, 60),
          opacity: s.opacity,
          pointerEvents: s.pointerEvents,
        });
      }
    }
    return hiding;
  };

  const buttons = [...document.querySelectorAll('button, [role="button"]')];
  console.log(`Total buttons/role=button: ${buttons.length}`);

  const listenButtons = [];
  const nearMisses = [];

  for (const btn of buttons) {
    const label = getLabel(btn);
    const vis = isVisible(btn);
    const effVis = isEffectivelyVisible(btn);
    const matchesListen = LISTEN_LABEL_PATTERN.test(label);
    const matchesExcluded = EXCLUDED_LABEL_PATTERN.test(label);
    const matchesIcon = hasListenIcon(btn);

    const hasRelevantText = /\b(listen|read|aloud|speaker|volume|tts|audio|play)\b/i.test(label);

    if ((matchesListen || matchesIcon) && !matchesExcluded) {
      const hiding = getHidingAncestors(btn);
      listenButtons.push({ btn, label, vis, effVis, matchesIcon, hiding });
    } else if (hasRelevantText || matchesListen || matchesIcon) {
      nearMisses.push({ btn, label, vis, effVis, matchesListen, matchesExcluded, matchesIcon });
    }
  }

  if (listenButtons.length) {
    console.log(`\n✅ LISTEN BUTTONS FOUND (${listenButtons.length}):`);
    for (const { btn, label, vis, effVis, matchesIcon, hiding } of listenButtons) {
      console.log(`  [${btn.tagName}] visible=${vis} effVisible=${effVis} iconMatch=${matchesIcon} label="${label.slice(0,100)}"`, btn);
      if (hiding.length) {
        console.log(`    ⚠️  Hidden by ${hiding.length} ancestor(s):`);
        for (const h of hiding) {
          console.log(`      [${h.tag}] class="${h.class}" opacity=${h.opacity} pointerEvents=${h.pointerEvents}`, h.element);
        }
      }
    }
  } else {
    console.log('\n❌ NO LISTEN BUTTON FOUND by extension selectors!');
  }

  if (nearMisses.length) {
    console.log(`\n⚠️  Near-miss buttons (audio-adjacent but not matched):`);
    for (const { btn, label, vis, effVis, matchesListen, matchesExcluded, matchesIcon } of nearMisses) {
      console.log(
        `  [${btn.tagName}] matchesListen=${matchesListen} matchesExcluded=${matchesExcluded} matchesIcon=${matchesIcon} visible=${vis} effVisible=${effVis}`,
        `\n    label: "${label.slice(0,120)}"`,
        btn
      );
    }
  }

  // Check response root selectors
  const RESPONSE_ROOT_SELECTORS = [
    '[data-message-author-role="model"]',
    '[data-message-author-role="assistant"]',
    '[data-response-index]',
    '[data-testid*="response" i]',
    '[class*="model-response" i]',
    '[class*="response-container" i]',
    '[class*="response" i]',
    'message-content',
    'bard-response',
  ];
  console.log('\n--- Response root selector matches ---');
  for (const sel of RESPONSE_ROOT_SELECTORS) {
    const count = document.querySelectorAll(sel).length;
    if (count) console.log(`  ✅ "${sel}": ${count} element(s)`);
  }

  // Composer detection
  const composers = [...document.querySelectorAll('textarea, [contenteditable="true"]')]
    .filter(isVisible);
  console.log(`\n--- Visible composer/textarea elements: ${composers.length} ---`);
  for (const c of composers) {
    console.log(`  [${c.tagName}] contenteditable="${c.getAttribute('contenteditable')}" placeholder="${c.getAttribute('placeholder')}"`, c);
  }

  // Dump all unique button labels to find what the actual listen button is labeled
  console.log('\n--- All unique button labels on page (find the listen/read-aloud one) ---');
  const seen = new Set();
  for (const btn of buttons) {
    const key = [
      btn.getAttribute('aria-label'),
      btn.getAttribute('title'),
      btn.getAttribute('data-tooltip'),
      btn.getAttribute('data-tooltip-text'),
    ].filter(Boolean).join('|');
    if (key && !seen.has(key)) {
      seen.add(key);
      console.log(`  "${key}"`, btn);
    }
  }

  // Check for Material icon buttons specifically
  console.log('\n--- Material icon buttons (mat-icon, fonticon, data-mat-icon-name) ---');
  const iconBtns = [...document.querySelectorAll('[data-mat-icon-name], [fonticon], button mat-icon')];
  const iconSeen = new Set();
  for (const el of iconBtns) {
    const name = el.getAttribute('data-mat-icon-name') || el.getAttribute('fonticon') || el.textContent?.trim() || '';
    const btn = el.closest('button, [role="button"]');
    const key = name + '|' + (btn?.getAttribute('aria-label') || '');
    if (!iconSeen.has(key)) {
      iconSeen.add(key);
      console.log(`  icon="${name}" button-label="${btn?.getAttribute('aria-label') || ''}" visible=${btn ? isVisible(btn) : 'N/A'}`, el);
    }
  }
})();
