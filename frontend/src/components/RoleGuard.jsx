/**
 * FabricShield AI - Role Guard
 * Renders children only if the user has a required role. UI-only; server enforces truly.
 */

import React from "react";
import { Box, Button, Typography } from "@mui/material";
import { Lock, ArrowBack } from "@mui/icons-material";
import { useNavigate } from "react-router-dom";
import { useRole } from "../hooks/useRole";

export default function RoleGuard({ roles = [], children, fallback }) {
  const { hasRole } = useRole();
  const navigate = useNavigate();

  if (!hasRole(...roles)) {
    if (fallback !== undefined) return fallback;
    return (
      <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", py: 10, color: "text.secondary" }}>
        <Lock sx={{ fontSize: 48, mb: 1, opacity: 0.3 }} />
        <Typography variant="h6">Access Restricted</Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          You need one of: {roles.join(", ")} to view this page.
        </Typography>
        <Button variant="outlined" startIcon={<ArrowBack />} onClick={() => navigate("/")}>
          Back to Dashboard
        </Button>
      </Box>
    );
  }
  return children;
}
