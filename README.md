# AI Auto Listen

A small Chrome (Manifest V3) extension that automatically starts text-to-speech when an AI chat response finishes:

- **Gemini** (`gemini.google.com`): clicks **Listen** in the response's "more" menu.
- **ChatGPT** (`chatgpt.com`, `chat.openai.com`): clicks **Read Aloud** once generation has stopped.

Responses that were already on the page when it loaded are skipped, so opening an old chat won't start reading it.

## Install

1. Open Chrome and go to `chrome://extensions`.
2. Turn on **Developer mode**.
3. Click **Load unpacked** and select this folder.
4. Open Gemini or ChatGPT and send a prompt.

Use the extension's toolbar popup to turn auto-listen on or off. The setting is stored with `chrome.storage.sync`.

If you change the files after loading the extension, click **Reload** on the extension's card at `chrome://extensions`, then refresh the chat tab.

## Permissions

- `storage`: remembers the on/off setting.
- Host access to Gemini and ChatGPT only, where the content script runs.

The extension clicks the page's own buttons with normal DOM events. It doesn't use the `debugger` permission and doesn't send data anywhere.

## Debugging

Set `DEBUG = true` at the top of `content.js` to show a small status overlay in the corner of the page.

`tests/` contains the Python/Playwright scripts and DevTools snippets used while working out each site's markup.

## Notes

Gemini and ChatGPT change their markup over time. The content script targets accessible labels and icons (`Listen`, `Read aloud`, the "more" menu icon) instead of generated CSS classes, but a site redesign can still break it. The ChatGPT strategy expects the English UI labels.
