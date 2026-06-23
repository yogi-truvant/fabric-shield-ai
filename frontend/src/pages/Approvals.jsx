/**
 * FabricShield AI - Approvals
 * Data grid with risk-colored entities, confidence bars, detection source,
 * tab-aware bulk actions (approve/reject/mask/unmask), and clear.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, LinearProgress, TextField, Typography,
} from "@mui/material";
import { Check, Close, DeleteSweep, Lock, LockOpen, Refresh } from "@mui/icons-material";
import { DataGrid, GridToolbar } from "@mui/x-data-grid";
import { useMsal } from "@azure/msal-react";
import { useSnackbar } from "notistack";
import { useSearchParams } from "react-router-dom";
import { approvalsApi } from "../services/api";
import RoleGuard from "../components/RoleGuard";
import { useRole } from "../hooks/useRole";

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  APPROVED: { color: "info", label: "Approved" },
  REJECTED: { color: "default", label: "Rejected" },
  MASKED: { color: "success", label: "Masked" },
  MASKING_FAILED: { color: "error", label: "Mask Failed" },
};

const ENTITY_COLORS = {
  SSN: "#d13438", EMAIL: "#0078d4", PHONE: "#8764b8", DATE_OF_BIRTH: "#ff8c00",
  CREDIT_CARD: "#d13438", IBAN: "#5c2d91", IP_ADDRESS: "#008272", PERSON_NAME: "#0078d4",
  LOCATION: "#008272", MEDICAL_RECORD: "#d13438", NPI: "#5c2d91", DEA: "#5c2d91", PHI_GENERIC: "#d13438",
};

const SOURCE_CONFIG = {
  both: { label: "Name + Content", color: "success" },
  content: { label: "Content", color: "info" },
  ml: { label: "Content (NER)", color: "info" },
  rule: { label: "Name", color: "default" },
};

export default function Approvals() {
  const { accounts } = useMsal();
  const { hasRole } = useRole();
  const { enqueueSnackbar } = useSnackbar();
  const [searchParams] = useSearchParams();
  const tenantId = accounts[0]?.tenantId || "";
  const canApprove = hasRole("approver", "admin");

  const initialStatus = searchParams.get("status");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState([]);
  const [statusFilter, setStatusFilter] = useState(
    initialStatus === "ALL" ? null : (initialStatus || "PENDING")
  );
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectDialog, setRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [clearDialog, setClearDialog] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    approvalsApi.listApprovals({ status_filter: statusFilter || undefined, limit: 500 })
      .then((res) => setRows(res.data.map((r) => ({ ...r, id: r.approval_id }))))
      .catch((err) => enqueueSnackbar(err.message, { variant: "error" }))
      .finally(() => setLoading(false));
  }, [statusFilter, enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  // Which bulk actions make sense for the current tab.
  const f = statusFilter;
  const showApprove = canApprove && (f === null || f === "PENDING" || f === "REJECTED");
  const showReject = canApprove && (f === null || f === "PENDING" || f === "APPROVED");
  const showMask = canApprove && (f === null || f === "APPROVED");
  const showUnmask = canApprove && (f === null || f === "MASKED");

  const runBulk = async (fn, verb) => {
    if (!selected.length) return;
    setActionLoading(true);
    try {
      const res = await fn();
      const d = res.data;
      if (d.processed === 0) {
        enqueueSnackbar(`Nothing to ${verb} in the selected rows`, { variant: "info" });
      } else {
        enqueueSnackbar(`${d.succeeded} ${verb}${verb.endsWith("e") ? "d" : "ed"}, ${d.failed} failed`,
          { variant: d.failed > 0 ? "warning" : "success" });
      }
      setSelected([]);
      load();
    } catch (err) {
      enqueueSnackbar(err.message, { variant: "error" });
    } finally {
      setActionLoading(false);
      setRejectDialog(false);
      setRejectReason("");
    }
  };

  const approveSel = () => runBulk(() => approvalsApi.bulkAction({ tenant_id: tenantId, approval_ids: selected, action: "approve" }), "approve");
  const rejectSel = (reason) => runBulk(() => approvalsApi.bulkAction({ tenant_id: tenantId, approval_ids: selected, action: "reject", rejection_reason: reason }), "reject");
  const maskSel = () => runBulk(() => approvalsApi.bulkMask({ approval_ids: selected }), "mask");
  const unmaskSel = () => runBulk(() => approvalsApi.bulkUnmask({ approval_ids: selected }), "unmask");

  const handleClear = async () => {
    try {
      const r = await approvalsApi.clear();
      enqueueSnackbar(`Cleared ${r.data.deleted} result(s) - re-scan to repopulate`, { variant: "info" });
      setSelected([]);
      load();
    } catch (err) {
      enqueueSnackbar(err.message, { variant: "error" });
    } finally {
      setClearDialog(false);
    }
  };

  const rowAction = async (apiCall, okMsg) => {
    try { await apiCall(); enqueueSnackbar(okMsg, { variant: "success" }); load(); }
    catch (err) { enqueueSnackbar(err.message, { variant: "error" }); }
  };

  const columns = [
    { field: "schema_name", headerName: "Table", width: 170, valueGetter: (_, row) => `${row.schema_name}.${row.table_name}` },
    { field: "column_name", headerName: "Column", width: 140, flex: 1 },
    {
      field: "entity_type", headerName: "PII Type", width: 140,
      renderCell: (p) => <Chip size="small" label={p.value}
        sx={{ backgroundColor: ENTITY_COLORS[p.value] || "#605e5c", color: "white", fontWeight: 700, fontSize: "0.7rem" }} />,
    },
    {
      field: "detection_source", headerName: "Source", width: 150,
      renderCell: (p) => {
        const cfg = SOURCE_CONFIG[p.value] || { label: p.value || "-", color: "default" };
        const pct = p.row.sample_match_pct != null ? ` ${Math.round(p.row.sample_match_pct * 100)}%` : "";
        return <Chip size="small" variant="outlined" color={cfg.color} label={cfg.label + pct} />;
      },
    },
    {
      field: "confidence", headerName: "Confidence", width: 120,
      renderCell: (p) => (
        <Box sx={{ width: "100%" }}>
          <Typography variant="caption" fontWeight={600}>{Math.round(p.value * 100)}%</Typography>
          <LinearProgress variant="determinate" value={p.value * 100}
            color={p.value >= 0.8 ? "error" : p.value >= 0.6 ? "warning" : "info"}
            sx={{ height: 6, borderRadius: 3 }} />
        </Box>
      ),
    },
    { field: "recommended_mask", headerName: "Mask", width: 80 },
    {
      field: "status", headerName: "Status", width: 120,
      renderCell: (p) => {
        const cfg = STATUS_CONFIG[p.value] || { color: "default", label: p.value };
        return <Chip size="small" label={cfg.label} color={cfg.color} />;
      },
    },
    { field: "created_at", headerName: "Detected", width: 160, valueFormatter: (v) => v ? new Date(v).toLocaleString() : "-" },
    {
      field: "actions", headerName: "Action", width: 110, sortable: false,
      renderCell: (p) => {
        if (!canApprove) return null;
        if (p.row.status === "APPROVED") {
          return <Button size="small" startIcon={<Lock />} color="success" onClick={(e) => {
            e.stopPropagation();
            rowAction(() => approvalsApi.applyMask(p.row.approval_id, p.row.connection_name, "azure_sql"), "Mask applied");
          }}>Mask</Button>;
        }
        if (p.row.status === "MASKED") {
          return <Button size="small" startIcon={<LockOpen />} color="warning" onClick={(e) => {
            e.stopPropagation();
            rowAction(() => approvalsApi.unmask(p.row.approval_id), "Mask removed");
          }}>Unmask</Button>;
        }
        return null;
      },
    },
  ];

  return (
    <RoleGuard roles={["analyst", "approver", "admin"]}>
      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Box>
            <Typography variant="h4">Approvals</Typography>
            <Typography variant="subtitle1" color="text.secondary">Review and action flagged PII / PHI columns</Typography>
          </Box>
          <Box sx={{ display: "flex", gap: 1 }}>
            {canApprove && (
              <Button startIcon={<DeleteSweep />} onClick={() => setClearDialog(true)} variant="outlined" color="error">
                Clear results
              </Button>
            )}
            <Button startIcon={<Refresh />} onClick={load} variant="outlined">Refresh</Button>
          </Box>
        </Box>

        <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap", alignItems: "center" }}>
          {[null, "PENDING", "APPROVED", "MASKED", "REJECTED"].map((s) => (
            <Chip key={s ?? "all"} label={s ? STATUS_CONFIG[s].label : "All"} onClick={() => { setSelected([]); setStatusFilter(s); }}
              color={statusFilter === s ? "primary" : "default"} variant={statusFilter === s ? "filled" : "outlined"} />
          ))}
          <Box sx={{ flex: 1 }} />
          <Typography variant="body2" color="text.secondary">{rows.length} column(s)</Typography>
        </Box>

        {canApprove && selected.length > 0 && (
          <Box sx={{ position: "sticky", top: 56, zIndex: 2, mb: 2 }}>
            <Alert severity="info" sx={{ boxShadow: 3 }}
              action={
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                  {showApprove && (
                    <Button size="small" color="success" variant="contained"
                      startIcon={actionLoading ? <CircularProgress size={14} color="inherit" /> : <Check />}
                      onClick={approveSel} disabled={actionLoading}>Approve {selected.length}</Button>
                  )}
                  {showReject && (
                    <Button size="small" color="error" variant="contained" startIcon={<Close />}
                      onClick={() => setRejectDialog(true)} disabled={actionLoading}>Reject {selected.length}</Button>
                  )}
                  {showMask && (
                    <Button size="small" color="secondary" variant="contained" startIcon={<Lock />}
                      onClick={maskSel} disabled={actionLoading}>Mask {selected.length}</Button>
                  )}
                  {showUnmask && (
                    <Button size="small" color="warning" variant="contained" startIcon={<LockOpen />}
                      onClick={unmaskSel} disabled={actionLoading}>Unmask {selected.length}</Button>
                  )}
                </Box>
              }>
              {selected.length} column(s) selected
            </Alert>
          </Box>
        )}

        <Box sx={{ height: 560, width: "100%" }}>
          <DataGrid
            rows={rows} columns={columns} loading={loading}
            checkboxSelection={canApprove} disableRowSelectionOnClick
            onRowSelectionModelChange={(ids) => setSelected(ids)} rowSelectionModel={selected}
            pageSizeOptions={[25, 50, 100]}
            initialState={{ pagination: { paginationModel: { pageSize: 25 } }, density: "comfortable" }}
            slots={{ toolbar: GridToolbar }} slotProps={{ toolbar: { showQuickFilter: true } }}
          />
        </Box>

        <Dialog open={rejectDialog} onClose={() => setRejectDialog(false)} maxWidth="xs" fullWidth>
          <DialogTitle>Reject {selected.length} column(s)</DialogTitle>
          <DialogContent>
            <TextField fullWidth multiline rows={3} label="Rejection reason (optional)"
              value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} sx={{ mt: 1 }} />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRejectDialog(false)}>Cancel</Button>
            <Button color="error" variant="contained" onClick={() => rejectSel(rejectReason)} disabled={actionLoading}>
              Confirm Reject
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog open={clearDialog} onClose={() => setClearDialog(false)} maxWidth="xs" fullWidth>
          <DialogTitle>Clear all results?</DialogTitle>
          <DialogContent>
            <Typography variant="body2">
              This removes all scan/approval records for your tenant so the next scan starts fresh.
              It does <strong>not</strong> remove masks already applied in the database - only
              FabricShield&apos;s tracking. This cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setClearDialog(false)}>Cancel</Button>
            <Button color="error" variant="contained" onClick={handleClear}>Clear results</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </RoleGuard>
  );
}
