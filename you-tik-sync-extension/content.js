// Content Script for You-Tik Session Sync Extension

// 1. Inject a global variable to let the You-Tik frontend know the extension is active
try {
  const script = document.createElement('script');
  script.textContent = 'window.__YOUTIK_SYNC_EXTENSION__ = true;';
  (document.head || document.documentElement).appendChild(script);
  script.remove();
} catch (e) {
  console.error("[You-Tik Content Script] Failed to inject active variable:", e);
}

// 2. Listen for events sent from the You-Tik frontend page
window.addEventListener("message", (event) => {
  // Only trust messages from the same window
  if (event.source !== window) return;

  if (event.data && event.data.type === "YOUTIK_TRIGGER_SYNC") {
    console.log("[You-Tik Content Script] Ingestion sync triggered. Extracting cookies...");
    
    // Send message to background service worker to fetch cookies securely
    chrome.runtime.sendMessage({ action: "sync_youtube_cookies" }, (response) => {
      if (chrome.runtime.lastError) {
        console.error("[You-Tik Content Script] Background messaging error:", chrome.runtime.lastError);
        window.postMessage({ 
          type: "YOUTIK_SYNC_RESULT", 
          success: false, 
          error: "Extension communications failed. Please reload YouTube and try again." 
        }, "*");
        return;
      }
      
      // Pass the extracted cookies back to the You-Tik website
      window.postMessage({ 
        type: "YOUTIK_SYNC_RESULT", 
        success: response.success, 
        cookies: response.cookies,
        error: response.error 
      }, "*");
    });
  }
});
