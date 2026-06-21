/**
 * FabricShield AI - Guide
 * Plain-language explanation of the product flow, each section, and what each role can do.
 */

import React from "react";
import {
  Box, Card, CardContent, Chip, Divider, Grid, Step, StepLabel, Stepper, Typography,
} from "@mui/material";
import {
  Approval, CheckCircle, Dashboard, HelpOutline, Lock, Security, Storage, TableChart,
} from "@mui/icons-material";
import { useRole } from "../hooks/useRole";

const FLOW = ["Connect a database", "Scan for PII", "Review & approve", "Apply masks", "Audit"];

const SECTIONS = [
  {
    icon: <Dashboard color="primary" />, title: "Dashboard",
    what: "Your at-a-glance view: how many PII/PHI columns were found, how many are masked, and how many still need review. The tiles are clickable and jump straight to the matching list.",
    role: "Everyone can view it.",
  },
  {
    icon: <Storage color="primary" />, title: "Connections",
    what: "Register the databases FabricShield is allowed to look at (server, database, and a least-privilege login). Use Test to confirm it's reachable. This is the one-time hook-up.",
    role: "Admins add/remove connections; others can view and test.",
  },
  {
    icon: <TableChart color="primary" />, title: "Scan",
    what: "Pick a connection and schemas, then Start. FabricShield reads only column names and types to flag likely PII/PHI. Turn on Deep content scan to also sample values (with consent) and catch mis-named columns like a card column called 'CC'.",
    role: "Analysts, Approvers and Admins can run scans.",
  },
  {
    icon: <Approval color="primary" />, title: "Approvals",
    what: "The human checkpoint. Every flagged column lands here. Review the PII type, confidence and source, then Approve (it should be masked), Reject (not sensitive), or Mask an approved one. Re-scanning never resurfaces already-masked columns.",
    role: "Approvers and Admins can approve/reject/mask; Analysts can view.",
  },
  {
    icon: <Security color="primary" />, title: "Audit Log",
    what: "An immutable record of every action — who scanned, approved, or masked what and when. Exportable to CSV for compliance.",
    role: "Everyone with access can view; records can never be edited or deleted.",
  },
];

const ROLES = [
  { role: "Viewer", color: "default", can: "View dashboards and results." },
  { role: "Analyst", color: "info", can: "Run scans, view everything." },
  { role: "Approver", color: "warning", can: "Approve / reject / apply masks." },
  { role: "Admin", color: "error", can: "Everything, plus manage connections." },
];

export default function Guide() {
  const { highestRole } = useRole();

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
        <HelpOutline color="primary" />
        <Typography variant="h4">How FabricShield works</Typography>
      </Box>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 3 }}>
        Find sensitive data, get a human to approve it, mask it — and keep a record. Here's the flow and what each part does.
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>The 5-step flow</Typography>
          <Stepper alternativeLabel>
            {FLOW.map((label) => (
              <Step key={label} active completed={false}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            FabricShield is data-blind by default — it reads only column metadata, never your rows, unless you explicitly turn on Deep content scan (which samples values in memory and never stores them).
          </Typography>
        </CardContent>
      </Card>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {SECTIONS.map((s) => (
          <Grid item xs={12} md={6} key={s.title}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                  {s.icon}
                  <Typography variant="h6">{s.title}</Typography>
                </Box>
                <Typography variant="body2" sx={{ mb: 1.5 }}>{s.what}</Typography>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, color: "text.secondary" }}>
                  <Lock sx={{ fontSize: 15 }} />
                  <Typography variant="caption">{s.role}</Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card>
        <CardContent>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <CheckCircle color="primary" />
            <Typography variant="h6">What you can do depends on your role</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            You are signed in as <Chip size="small" label={highestRole} color="primary" sx={{ height: 20 }} />. Higher roles include everything below them.
          </Typography>
          <Divider sx={{ mb: 1.5 }} />
          {ROLES.map((r) => (
            <Box key={r.role} sx={{ display: "flex", alignItems: "center", gap: 1.5, py: 0.75 }}>
              <Chip size="small" label={r.role} color={r.color} sx={{ minWidth: 84 }} />
              <Typography variant="body2">{r.can}</Typography>
            </Box>
          ))}
        </CardContent>
      </Card>
    </Box>
  );
}
