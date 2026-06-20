/**
 * FabricShield AI - MSAL Configuration
 * Multi-tenant Entra ID authentication using @azure/msal-browser.
 */

import { LogLevel } from "@azure/msal-browser";

/**
 * MSAL configuration object. Values are injected via Vite env vars at build time.
 * Set these in .env or Azure App Service app settings.
 */
export const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    // Multi-tenant: use "common" to allow ANY Entra ID tenant to sign in
    authority: "https://login.microsoftonline.com/common",
    redirectUri: import.meta.env.VITE_REDIRECT_URI || window.location.origin,
    postLogoutRedirectUri: window.location.origin,
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: "sessionStorage", // sessionStorage preferred over localStorage for security
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        switch (level) {
          case LogLevel.Error:
            console.error("[MSAL]", message);
            break;
          case LogLevel.Warning:
            console.warn("[MSAL]", message);
            break;
          default:
            if (import.meta.env.DEV) console.info("[MSAL]", message);
        }
      },
      logLevel: import.meta.env.DEV ? LogLevel.Info : LogLevel.Warning,
    },
  },
};

/**
 * Scopes requested when acquiring tokens for the backend API.
 * The scope must match the API's App ID URI configured in the App Registration.
 */
export const apiScopes = [
  `api://${import.meta.env.VITE_AZURE_CLIENT_ID}/access_as_user`,
];

/**
 * Login request config - includes the API scope so we get both
 * an ID token and an access token in one round-trip.
 */
export const loginRequest = {
  scopes: apiScopes,
  prompt: "select_account",
};
