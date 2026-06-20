/**
 * FabricShield AI - API Client
 * Axios instance with automatic Bearer token injection via MSAL.
 * All requests include the tenant context header.
 */

import axios from "axios";
import { msalInstance } from "../main";
import { apiScopes } from "../auth/msalConfig";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

// ── Request interceptor: inject Bearer token ──────────────────────────────────
apiClient.interceptors.request.use(async (config) => {
  const accounts = msalInstance.getAllAccounts();
  if (!accounts.length) return config;

  try {
    const tokenResponse = await msalInstance.acquireTokenSilent({
      scopes: apiScopes,
      account: accounts[0],
    });
    config.headers["Authorization"] = `Bearer ${tokenResponse.accessToken}`;
    config.headers["X-Tenant-ID"] = accounts[0].tenantId;
  } catch (err) {
    // Silent acquisition failed - redirect to login
    console.warn("Token refresh failed, redirecting to login", err);
    await msalInstance.acquireTokenRedirect({ scopes: apiScopes });
  }
  return config;
});

// ── Response interceptor: normalize errors ────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail || error.message;
    const status = error.response?.status;
    return Promise.reject({ message: detail, status, raw: error });
  }
);

// ── API Methods ───────────────────────────────────────────────────────────────

export const scanApi = {
  triggerScan: (payload) => apiClient.post("/scan", payload),
  getScan: (scanId) => apiClient.get(`/scan/${scanId}`),
  listScans: (limit = 20) => apiClient.get("/scans", { params: { limit } }),
};

export const approvalsApi = {
  listApprovals: (params = {}) => apiClient.get("/approvals", { params }),
  bulkAction: (payload) => apiClient.post("/approvals/bulk", payload),
  applyMask: (approvalId, connectionName, dbType) =>
    apiClient.post(`/approvals/${approvalId}/mask`, null, {
      params: { connection_name: connectionName, db_type: dbType },
    }),
  getStats: () => apiClient.get("/approvals/stats"),
};

export const connectionsApi = {
  list: () => apiClient.get("/connections"),
  create: (payload) => apiClient.post("/connections", payload),
  test: (name, dbType = "azure_sql") => apiClient.post(`/connections/${name}/test`, null, { params: { db_type: dbType } }),
  remove: (name) => apiClient.delete(`/connections/${name}`),
};

export const auditApi = {
  getLogs: (params = {}) => apiClient.get("/audit", { params }),
};

export const powerBiApi = {
  getEmbedToken: () => apiClient.get("/powerbi/token"),
};

export default apiClient;
