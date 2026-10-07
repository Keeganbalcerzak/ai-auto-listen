const enabledInput = document.querySelector('#enabled');
const statusText = document.querySelector('#status');

const setStatus = (enabled) => {
  statusText.textContent = enabled ? 'Listening will start after each new AI response.' : 'Auto-listen is off.';
};

chrome.storage.sync.get({ geminiAutoListenEnabled: true }, (result) => {
  enabledInput.checked = Boolean(result.geminiAutoListenEnabled);
  setStatus(enabledInput.checked);
});

enabledInput.addEventListener('change', () => {
  const enabled = enabledInput.checked;

  chrome.storage.sync.set({ geminiAutoListenEnabled: enabled }, () => {
    setStatus(enabled);
  });
});
