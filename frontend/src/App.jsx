/**
 * FabricShield AI - App Root
 * MSAL-protected routing, light/dark theme, global toasts.
 */

import React, { useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ThemeProvider, CssBaseline, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { Shield, VerifiedUser, Lock, Visibility } from "@mui/icons-material";
import { SnackbarProvider } from "notistack";

import { getTheme } from "./theme";
import { ColorModeContext } from "./colorMode";
import { loginRequest } from "./auth/msalConfig";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import Dashboard from "./pages/Dashboard";
import Scan from "./pages/Scan";
import Approvals from "./pages/Approvals";
import Audit from "./pages/Audit";
import Connections from "./pages/Connections";
import Guide from "./pages/Guide";

function TrustPill({ icon, text }) {
  return (
    <Stack direction="row" spacing={0.5} alignItems="center" sx={{ color: "text.secondary" }}>
      {icon}
      <Typography variant="caption">{text}</Typography>
    </Stack>
  );
}

function LoginPage() {
  const { instance, inProgress } = useMsal();
  return (
    <Box sx={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg, #004578 0%, #0078d4 55%, #2b88d8 100%)", p: 2,
    }}>
      <Box sx={{
        bgcolor: "white", p: 6, borderRadius: 3, textAlign: "center", maxWidth: 440, width: "100%",
        boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
      }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1, mb: 2 }}>
          <Shield sx={{ color: "primary.main", fontSize: 44 }} />
          <Typography variant="h4" fontWeight={700} color="primary.main">FabricShield</Typography>
        </Box>
        <Typography variant="h6" gutterBottom>AI Governance Platform</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
          Enterprise PII / PHI detection and masking for Azure SQL and Microsoft Fabric
        </Typography>
        {inProgress === "login" ? (
          <CircularProgress />
        ) : (
          <Button variant="contained" size="large" fullWidth onClick={() => instance.loginRedirect(loginRequest)} sx={{ py: 1.5, fontSize: "1rem" }}>
            Sign in with Microsoft
          </Button>
        )}
        <Stack direction="row" spacing={2} justifyContent="center" sx={{ mt: 3 }}>
          <TrustPill icon={<VerifiedUser sx={{ fontSize: 16 }} />} text="Metadata-only" />
          <TrustPill icon={<Lock sx={{ fontSize: 16 }} />} text="HIPAA-aligned" />
          <TrustPill icon={<Visibility sx={{ fontSize: 16, textDecoration: "line-through" }} />} text="No row data" />
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: "block" }}>
          Secured by Azure Entra ID
        </Typography>
      </Box>
    </Box>
  );
}

export default function App() {
  const [mode, setMode] = useState(() => {
    try { return localStorage.getItem("fsai-theme") || "light"; } catch { return "light"; }
  });
  const colorMode = useMemo(() => ({
    mode,
    toggle: () => setMode((m) => {
      const next = m === "light" ? "dark" : "light";
      try { localStorage.setItem("fsai-theme", next); } catch (e) { /* ignore */ }
      return next;
    }),
  }), [mode]);
  const appTheme = useMemo(() => getTheme(mode), [mode]);

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={appTheme}>
        <CssBaseline />
        <SnackbarProvider maxSnack={3} autoHideDuration={4000} anchorOrigin={{ vertical: "bottom", horizontal: "right" }}>
          <UnauthenticatedTemplate><LoginPage /></UnauthenticatedTemplate>
          <AuthenticatedTemplate>
            <BrowserRouter>
              <Layout>
                <ErrorBoundary>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/scan" element={<Scan />} />
                    <Route path="/connections" element={<Connections />} />
                    <Route path="/approvals" element={<Approvals />} />
                    <Route path="/audit" element={<Audit />} />
                    <Route path="/guide" element={<Guide />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </ErrorBoundary>
              </Layout>
            </BrowserRouter>
          </AuthenticatedTemplate>
        </SnackbarProvider>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}
