// Background Service Worker for You-Tik Session Sync Extension

// Generic handler for extracting cookies from multiple domains
function extractCookiesForDomains(domains, sendResponse) {
  let allCookies = [];
  let completedRequests = 0;
  
  if (!domains || domains.length === 0) {
    sendResponse({ success: false, error: "No domains specified for extraction." });
    return;
  }
  
  domains.forEach(domain => {
    chrome.cookies.getAll({ domain: domain }, (cookies) => {
      if (cookies) {
        allCookies = [...allCookies, ...cookies];
      }
      completedRequests++;
      
      if (completedRequests === domains.length) {
        if (allCookies.length === 0) {
          sendResponse({ 
            success: false, 
            error: `No cookies found. Please ensure you are logged into the platform in this browser.` 
          });
          return;
        }
        
        // Format cookies to standard Playwright JSON structure
        const formattedCookies = allCookies.map(c => ({
          domain: c.domain,
          expirationDate: c.expirationDate || (Date.now() / 1000 + 86400 * 30),
          hostOnly: !c.domain.startsWith("."),
          httpOnly: c.httpOnly,
          name: c.name,
          path: c.path,
          sameSite: c.sameSite === "no_restriction" ? "no_restriction" : "unspecified",
          secure: c.secure,
          session: c.session,
          value: c.value
        }));
        
        console.log(`[You-Tik Extension] Successfully extracted ${formattedCookies.length} cookies.`);
        sendResponse({ 
          success: true, 
          cookies: JSON.stringify(formattedCookies) 
        });
      }
    });
  });
}

function handleSyncRequest(request, sendResponse) {
  let domains = [];
  const action = request.action;
  const platform = request.platform ? request.platform.toLowerCase() : "";
  
  if (action === "sync_youtube_cookies" || (action === "sync_cookies" && platform === "youtube")) {
    domains = [".youtube.com", ".google.com"];
  } else if (action === "sync_tiktok_cookies" || (action === "sync_cookies" && platform === "tiktok")) {
    domains = [".tiktok.com"];
  } else if (action === "sync_instagram_cookies" || (action === "sync_cookies" && platform === "instagram")) {
    domains = [".instagram.com", ".facebook.com"];
  } else if (action === "sync_twitter_cookies" || (action === "sync_cookies" && platform === "twitter")) {
    domains = [".twitter.com", ".x.com"];
  } else {
    return false; // Action not supported
  }
  
  extractCookiesForDomains(domains, sendResponse);
  return true; // Keep message channel open for async response
}

// Listen for messages from our CONTENT SCRIPT (internal communication)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("[You-Tik Extension] Received message from content script:", request);
  return handleSyncRequest(request, sendResponse);
});

// Listen for messages directly from the WEBSITE (external communication)
chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  console.log("[You-Tik Extension] Received external message:", request);
  return handleSyncRequest(request, sendResponse);
});

