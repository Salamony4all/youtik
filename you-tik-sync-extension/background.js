// Background Service Worker for You-Tik Session Sync Extension

// Unified handler for fetching and formatting YouTube/Google cookies
function handleCookieExtraction(sendResponse) {
  // 1. Fetch all cookies for the .youtube.com domain
  chrome.cookies.getAll({ domain: ".youtube.com" }, (youtubeCookies) => {
    // 2. Fetch all cookies for the .google.com domain
    chrome.cookies.getAll({ domain: ".google.com" }, (googleCookies) => {
      
      const allCookies = [...youtubeCookies, ...googleCookies];
      
      if (allCookies.length === 0) {
        sendResponse({ 
          success: false, 
          error: "No cookies found. Please ensure you are logged into YouTube in this browser." 
        });
        return;
      }

      // 3. Format cookies to standard JSON structure compatible with our backend parser
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

      console.log(`[You-Tik Extension] Successfully extracted and formatted ${formattedCookies.length} cookies.`);
      
      sendResponse({ 
        success: true, 
        cookies: JSON.stringify(formattedCookies) 
      });
    });
  });
}

// Listen for messages from our CONTENT SCRIPT (internal communication)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("[You-Tik Extension] Received message from content script:", request);
  if (request.action === "sync_youtube_cookies") {
    handleCookieExtraction(sendResponse);
    return true; // Keep message channel open for async response
  }
});

// Listen for messages directly from the WEBSITE (external communication)
chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  console.log("[You-Tik Extension] Received external message:", request);
  if (request.action === "sync_youtube_cookies") {
    handleCookieExtraction(sendResponse);
    return true; // Keep message channel open for async response
  }
});
