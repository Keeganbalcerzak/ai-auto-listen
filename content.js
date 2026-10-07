(() => {
  let enabled = true;
  let processing = false;
  let observer = null;
  let timeoutId = null;

  // --- DEBUG OVERLAY ---
  const DEBUG = false; // set true to show the on-page status overlay
  let debugOverlay = null;
  const initDebugOverlay = () => {
    if (!DEBUG || document.getElementById('gemini-autolisten-debug')) return;
    debugOverlay = document.createElement('div');
    debugOverlay.id = 'gemini-autolisten-debug';
    debugOverlay.style.cssText = 'position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.85); color: #0f0; z-index: 9999999; padding: 15px; font-family: monospace; font-size: 12px; border: 1px solid #0f0; border-radius: 5px; pointer-events: none; max-width: 300px; word-wrap: break-word; line-height: 1.4;';
    document.body.appendChild(debugOverlay);
  };
  const updateDebug = (status, extra = '') => {
    if (!debugOverlay) return;
    debugOverlay.innerHTML = `
      <b style="color:white">AI Auto Listen 1.5.0 Debug</b><br><br>
      <b>Enabled:</b> ${enabled}<br>
      <b>Status:</b> ${status}<br>
      ${extra ? `<b>Details:</b> ${extra}` : ''}
    `;
  };
  // ---------------------

  const getSetting = () =>
    new Promise((resolve) => {
      if (!globalThis.chrome?.storage?.sync) {
        resolve(true);
        return;
      }
      globalThis.chrome.storage.sync.get({ geminiAutoListenEnabled: true }, (result) => {
        resolve(Boolean(result.geminiAutoListenEnabled));
      });
    });

  const sleep = (delay) => new Promise((resolve) => window.setTimeout(resolve, delay));

  const geminiStrategy = {
    setup: () => {
      observer = new MutationObserver((mutations) => {
        if (!enabled) return;
        if (geminiStrategy.isNewResponseAdded(mutations)) {
          if (timeoutId) clearTimeout(timeoutId);
          timeoutId = setTimeout(geminiStrategy.processLatestResponse, 1000);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    },
    isNewResponseAdded: (mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType === 1) {
            if (node.matches?.('mat-icon[fonticon="more_horiz"]') || node.querySelector?.('mat-icon[fonticon="more_horiz"]')) {
              return true;
            }
          }
        }
      }
      return false;
    },
    markExistingAsProcessed: () => {
      const icons = document.querySelectorAll('mat-icon[fonticon="more_horiz"]');
      for (const icon of icons) {
        const trackingNode = icon.closest('button')?.parentElement || icon.parentElement || icon;
        trackingNode.dataset.autoListenProcessed = 'true';
      }
    },
    processLatestResponse: async () => {
      if (!enabled || processing) return;

      const icons = document.querySelectorAll('mat-icon[fonticon="more_horiz"]');
      if (icons.length === 0) return;

      const lastIcon = icons[icons.length - 1];
      const menuTrigger = lastIcon.closest('button') || lastIcon;
      const trackingNode = menuTrigger.parentElement || menuTrigger;

      if (!trackingNode.dataset.autoListenProcessed) {
        trackingNode.dataset.autoListenProcessed = 'true';
        
        const isPlaying = document.querySelectorAll('mat-icon[fonticon="pause"]').length > 0;
        if (isPlaying) {
          updateDebug('Completed', 'Already playing (user override)');
          setTimeout(() => updateDebug(enabled ? 'Waiting for response' : 'Disabled'), 3000);
          return;
        }
        
        processing = true;
        try {
          updateDebug('Processing (Opening Menu)');
          menuTrigger.click();

          let ttsButton = null;
          for (let i = 0; i < 15; i++) {
            await sleep(100);
            ttsButton = document.querySelector('gem-menu-item[data-test-id="tts-button"], gem-menu-item[value="tts"]');
            if (ttsButton) break;
          }

          if (ttsButton) {
            updateDebug('Processing (Clicking TTS)');
            ttsButton.click();
            await sleep(500);
            updateDebug('Completed', 'Gemini playback started');
          } else {
            updateDebug('Error', 'TTS menu item not found');
            menuTrigger.click(); // close menu
          }
        } catch (e) {
          updateDebug('Error', e.message);
        } finally {
          processing = false;
          setTimeout(() => updateDebug(enabled ? 'Waiting for response' : 'Disabled'), 3000);
        }
      }
    }
  };

  const chatGPTStrategy = {
    setup: () => {
      setInterval(chatGPTStrategy.poll, 1000);
    },
    markExistingAsProcessed: () => {
      const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
      for (const msg of messages) {
        msg.dataset.autoListenProcessed = msg.getAttribute('data-message-id') || 'processed';
      }
    },
    poll: async () => {
      if (!enabled || processing) return;

      const isVisible = (elem) => {
        if (!elem) return false;
        const rect = elem.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        const style = window.getComputedStyle(elem);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        
        // Check parent as well since ChatGPT often hides the wrapper
        if (elem.parentElement) {
          const parentStyle = window.getComputedStyle(elem.parentElement);
          if (parentStyle.display === 'none' || parentStyle.visibility === 'hidden' || parentStyle.opacity === '0') return false;
        }
        return true;
      };

      const stopBtn = document.querySelector('button[aria-label*="Stop generating" i]');
      const isStreaming = isVisible(stopBtn);
      
      if (isStreaming) {
         updateDebug('Waiting for response', 'Generation in progress (Stop generating button is visible)...');
         return;
      }

      const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
      if (messages.length === 0) return;

      const lastMessage = messages[messages.length - 1];
      const messageId = lastMessage.getAttribute('data-message-id') || 'processed';
      
      if (lastMessage.dataset.autoListenProcessed === messageId) return;

      processing = true;
      try {
        updateDebug('Processing', 'Hovering message');
        
        lastMessage.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
        lastMessage.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
        lastMessage.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));

        await sleep(250);

        // Check for direct Read Aloud button first (remove <button> tag requirement!)
        const directBtns = document.querySelectorAll('[aria-label*="Read aloud" i], [title*="Read aloud" i], [data-testid*="read" i]');
        let readAloudBtn = directBtns.length > 0 ? directBtns[directBtns.length - 1] : null;
        
        // If not found, it might be in the "More actions" menu!
        if (!readAloudBtn) {
           const moreActionsBtns = document.querySelectorAll('[aria-label*="More actions" i], [title*="More actions" i]');
           if (moreActionsBtns.length > 0) {
             const moreActionsBtn = moreActionsBtns[moreActionsBtns.length - 1];
             updateDebug('Processing', 'Opening More actions menu');
             
             moreActionsBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
             moreActionsBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
             
             await sleep(300); // Wait for dropdown to render
             
             const menuItems = document.querySelectorAll('[role="menuitem"][aria-label*="Read aloud" i], [role="menuitem"][title*="Read aloud" i]');
             if (menuItems.length > 0) {
                readAloudBtn = menuItems[menuItems.length - 1];
             } else {
                moreActionsBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
                moreActionsBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
             }
           }
        }

        if (!readAloudBtn) {
          updateDebug('Error', 'Read Aloud button not found. Is your ChatGPT language English?');
          processing = false;
          return;
        }

        if (readAloudBtn.disabled || readAloudBtn.getAttribute('aria-disabled') === 'true') {
           updateDebug('Processing', 'Waiting for button to enable');
           processing = false;
           return; 
        }

        updateDebug('Processing', 'Clicking Read Aloud!');
        readAloudBtn.click();
        readAloudBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
        readAloudBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
        
        lastMessage.dataset.autoListenProcessed = messageId;
        
        await sleep(500);
        updateDebug('Completed', 'ChatGPT playback started');
      } catch (e) {
        updateDebug('Error', e.message);
      } finally {
        processing = false;
      }
    }
  };

  const getActiveStrategy = () => {
    const host = window.location.hostname;
    if (host.includes('chatgpt.com') || host.includes('chat.openai.com')) {
      return chatGPTStrategy;
    }
    return geminiStrategy;
  };

  const strategy = getActiveStrategy();

  const start = async () => {
    initDebugOverlay();
    updateDebug('Initializing...');

    enabled = await getSetting();
    
    strategy.markExistingAsProcessed();

    updateDebug(enabled ? 'Waiting for response' : 'Disabled');

    strategy.setup();

    globalThis.chrome?.storage?.onChanged?.addListener((changes, areaName) => {
      if (areaName !== 'sync' || !changes.geminiAutoListenEnabled) return;
      enabled = Boolean(changes.geminiAutoListenEnabled.newValue);
      
      if (enabled) {
        updateDebug('Waiting for response');
      } else {
        updateDebug('Disabled');
      }
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
