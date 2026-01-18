/**
 * Background service worker for Cookie Extractor extension.
 * Handles cookie retrieval using chrome.cookies API.
 */

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getCookies") {
    getCookiesForDomain(request.domain)
      .then((cookies) => {
        sendResponse({ success: true, cookies: cookies });
      })
      .catch((error) => {
        sendResponse({ success: false, error: error.message });
      });
    return true; // Keep message channel open for async response
  }

  if (request.action === "extractComplete") {
    // Store extracted data for retrieval by automation script
    chrome.storage.local.set({
      extractedData: request.data,
      extractedAt: Date.now(),
    });
    console.log("[CookieExtractor] Data stored:", request.data);
    sendResponse({ success: true });
    return true;
  }
});

/**
 * Get all cookies for a domain using chrome.cookies API.
 * This can access httpOnly cookies.
 */
async function getCookiesForDomain(domain) {
  const cookies = await chrome.cookies.getAll({ domain: domain });

  const result = {};
  for (const cookie of cookies) {
    result[cookie.name] = cookie.value;
  }

  return result;
}

// Listen for page navigation to auto-extract
chrome.webNavigation.onCompleted.addListener(
  (details) => {
    // Notify content script that page is ready
    chrome.tabs.sendMessage(details.tabId, { action: "pageReady" });
  },
  { url: [{ hostContains: "business.gemini.google" }] }
);

console.log("[CookieExtractor] Background service worker started");
