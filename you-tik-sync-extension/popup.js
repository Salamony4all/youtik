document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-sync-youtube').addEventListener('click', () => triggerSync('youtube'));
  document.getElementById('btn-sync-tiktok').addEventListener('click', () => triggerSync('tiktok'));
});

function triggerSync(platform) {
  const statusEl = document.getElementById('status');
  statusEl.style.display = 'block';
  statusEl.className = 'status';
  statusEl.textContent = `Extracting ${platform} cookies...`;
  
  // We send a message to the background script to extract the cookies
  chrome.runtime.sendMessage({ action: "sync_cookies", platform: platform }, (response) => {
    if (chrome.runtime.lastError || !response) {
      statusEl.className = 'status error';
      statusEl.textContent = 'Error: ' + (chrome.runtime.lastError ? chrome.runtime.lastError.message : 'Unknown error');
      return;
    }
    
    if (response.success) {
      statusEl.textContent = 'Cookies extracted! Posting to You-Tik tab...';
      
      // Find the active You-Tik tab and post the message to it.
      // This allows the extension to popup and still use the website's API_BASE.
      chrome.tabs.query({ url: ["http://localhost/*", "https://*.up.railway.app/*"] }, (tabs) => {
        if (tabs.length === 0) {
          statusEl.className = 'status error';
          statusEl.textContent = 'Please open You-Tik in a browser tab first!';
          return;
        }
        
        // Inject script to pass the cookies to the first matching You-Tik tab
        const targetTab = tabs[0];
        chrome.scripting.executeScript({
          target: { tabId: targetTab.id },
          func: (syncPlatform, success, cookies, error) => {
            window.postMessage({ 
              type: "YOUTIK_SYNC_RESULT", 
              success: success, 
              cookies: cookies,
              platform: syncPlatform,
              error: error 
            }, "*");
          },
          args: [platform, response.success, response.cookies, response.error]
        }, () => {
          statusEl.textContent = '✅ Synced to You-Tik Tab!';
          setTimeout(() => {
            // Focus the tab and close popup
            chrome.tabs.update(targetTab.id, { active: true });
            window.close();
          }, 1000);
        });
      });
      
    } else {
      statusEl.className = 'status error';
      statusEl.textContent = 'Failed: ' + response.error;
    }
  });
}
