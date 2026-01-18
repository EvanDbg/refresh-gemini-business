/**
 * Content script for Cookie Extractor extension.
 * Extracts page information and coordinates with background script.
 */

(function () {
    "use strict";

    console.log("[CookieExtractor] Content script loaded");

    /**
     * Extract data from current page URL and DOM.
     */
    function extractPageData() {
        const url = window.location.href;
        const data = {
            url: url,
            userAgent: navigator.userAgent,
            timestamp: new Date().toISOString(),
        };

        // Extract team_id (cid) from URL
        // Pattern: /home/cid/TEAM_ID?csesidx=...
        const cidMatch = url.match(/\/cid\/([^/?]+)/);
        if (cidMatch) {
            data.config_id = cidMatch[1];
        }

        // Extract csesidx from URL params
        const urlParams = new URLSearchParams(window.location.search);
        const csesidx = urlParams.get("csesidx");
        if (csesidx) {
            data.csesidx = csesidx;
        }

        return data;
    }

    /**
     * Request cookies from background script.
     */
    async function getCookies() {
        return new Promise((resolve) => {
            chrome.runtime.sendMessage(
                { action: "getCookies", domain: ".google.com" },
                (response) => {
                    if (response && response.success) {
                        resolve(response.cookies);
                    } else {
                        console.error("[CookieExtractor] Failed to get cookies");
                        resolve({});
                    }
                }
            );
        });
    }

    /**
     * Main extraction function.
     */
    async function performExtraction() {
        console.log("[CookieExtractor] Starting extraction...");

        // Get page data
        const pageData = extractPageData();

        // Get cookies from background
        const cookies = await getCookies();

        // Combine data
        const extractedData = {
            ...pageData,
            secure_c_ses: cookies["__Secure-C_SES"] || "",
            host_c_oses: cookies["__Host-C_OSES"] || "",
        };

        console.log("[CookieExtractor] Extracted data:", extractedData);

        // Send to background for storage
        chrome.runtime.sendMessage({
            action: "extractComplete",
            data: extractedData,
        });

        // Also expose in page for Playwright to read
        window.__geminiExtractedData = extractedData;

        // Create a custom event for Playwright to listen
        window.dispatchEvent(
            new CustomEvent("geminiDataExtracted", {
                detail: extractedData,
            })
        );

        return extractedData;
    }

    // Listen for page ready message from background
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "pageReady") {
            performExtraction();
        }
        if (request.action === "extract") {
            performExtraction().then((data) => {
                sendResponse({ success: true, data: data });
            });
            return true;
        }
    });

    // Also run on initial load if we're on the right page
    if (window.location.href.includes("business.gemini.google/home/cid")) {
        // Wait a bit for page to fully load
        setTimeout(performExtraction, 2000);
    }
})();
