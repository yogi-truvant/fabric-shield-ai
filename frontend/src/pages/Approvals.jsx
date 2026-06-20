/**
 * FabricShield AI - Approvals
 * Data grid with risk-colored entities, confidence bars, bulk approve/reject, masking.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, LinearProgress, TextField, Typography,
} from "@mui/material";
import { Check, Close, Lock, Refresh } from "@mui/icons-material";
import { DataGrid, GridToolbar } from "@mui/x-data-grid";
import { useMsal } from "@azure/msal-react";
import { useSnackbar } from "notistack";
import { approvalsApi } from "../services/api";
import RoleGuard from "../components/RoleGuard";
import { useRole } from "../hooks/useRole";

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  APPROVED: { color: "info", label: "Approved" },
  REJECTED: { color: "error", label: "Rejected" },
  MASKED: { color: "success", label: "Masked" },
  MASKING_FAILED: { color: "error", label: "Mask Failed" },
};

const ENTITY_COLORS = {
  SSN: "#d13438", EMAIL: "#0078d4", PHONE: "#8764b8", DATE_OF_BIRTH: "#ff8c00",
  CREDIT_CARD: "#d13438", IBAN: "#5c2d91", IP_ADDRESS: "#008272", PERSON_NAME: "#0078d4",
  LOCATION: "#008272", MEDICAL_RECORD: "#d13438", NPI: "#5c2d91", DEA: "#5c2d91", PHI_GENERIC: "#d13438",
};

export default function Approvals() {
  const { accounts } = useMsal();
  const { hasRole } = useRole();
  const { enqueueSnackbar } = useSnackbar();
  const tenantId = accounts[0]?.tenantId || "";
  const canApprove = hasRole("approver", "admin");

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectDialog, setRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    approvalsApi.listApprovals({ status_filter: statusFilter || undefined, limit: 500 })
      .then((res) => setRows(res.data.map((r) => ({ ...r, id: r.approval_id }))))
      .catch((err) => enqueueSnackbar(err.message, { variant: "error" }))
      .finally(() => setLoading(false));
  }, [statusFilter, enqueueSnackbar]);

  useEffect(() => { load(); }, [load]);

  const handleBulkAction = async (action, reason) => {
    if (!selected.length) return;
    setActionLoading(true);
    try {
      const res = await approvalsApi.bulkAction({ tenant_id: tenantId, approval_ids: selected, action, rejection_reason: reason });
      const d = res.data;
      enqueueSnackbar(`${d.succeeded} ${action}d, ${d.failed} failed`, { variant: d.failed > 0 ? "warning" : "success" });
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

  const columns = [
    { field: "schema_name", headerName: "Table", width: 170, valueGetter: (_, row) => `${row.schema_name}.${row.table_name}` },
    { field: "column_name", headerName: "Column", width: 150, flex: 1 },
    {
      field: "entity_type", headerName: "PII Type", width: 150,
      renderCell: (p) => <Chip size="small" label={p.value}
        sx={{ backgroundColor: ENTITY_COLORS[p.value] || "#605e5c", color: "white", fontWeight: 700, fontSize: "0.7rem" }} />,
    },
    {
      field: "confidence", headerName: "Confidence", width: 130,
      renderCell: (p) => (
        <Box sx={{ width: "100%" }}>
          <Typography variant="caption" fontWeight={600}>{Math.round(p.value * 100)}%</Typography>
          <LinearProgress variant="determinate" value={p.value * 100}
            color={p.value >= 0.8 ? "error" : p.value >= 0.6 ? "warning" : "info"}
            sx={{ height: 6, borderRadius: 3 }} />
        </Box>
      ),
    },
    { field: "recommended_mask", headerName: "Mask", width: 90 },
    {
      field: "status", headerName: "Status", width: 120,
      renderCell: (p) => {
        const cfg = STATUS_CONFIG[p.value] || { color: "default", label: p.value };
        return <Chip size="small" label={cfg.label} color={cfg.color} />;
      },
    },
    { field: "created_at", headerName: "Detected", width: 160, valueFormatter: (v) => v ? new Date(v).toLocaleString() : "-" },
    {
      field: "actions", headerName: "Action", width: 100, sortable: false,
      renderCell: (p) => p.row.status === "APPROVED" && canApprove ? (
        <Button size="small" startIcon={<Lock />} color="success" onClick={async (e) => {
          e.stopPropagation();
          try { await approvalsApi.applyMask(p.row.approval_id, p.row.connection_name, "azure_sql");
            enqueueSnackbar("Mask applied", { variant: "success" }); load();
          } catch (err) { enqueueSnackbar(err.message, { variant: "error" }); }
        }}>Mask</Button>
      ) : null,
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
          <Button startIcon={<Refresh />} onClick={load} variant="outlined">Refresh</Button>
        </Box>

        <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap", alignItems: "center" }}>
          {[null, "PENDING", "APPROVED", "MASKED", "REJECTED"].map((s) => (
            <Chip key={s ?? "all"} label={s ?? "All"} onClick={() => setStatusFilter(s)}
              color={statusFilter === s ? "primary" : "default"} variant={statusFilter === s ? "filled" : "outlined"} />
          ))}
          <Box sx={{ flex: 1 }} />
          <Typography variant="body2" color="text.secondary">{rows.length} column(s)</Typography>
        </Box>

        {canApprove && selected.length > 0 && (
          <Box sx={{ position: "sticky", top: 56, zIndex: 2, mb: 2 }}>
            <Alert severity="info" sx={{ boxShadow: 3 }}
              action={
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Button size="small" color="success" variant="contained"
                    startIcon={actionLoading ? <CircularProgress size={14} color="inherit" /> : <Check />}
                    onClick={() => handleBulkAction("approve")} disabled={actionLoading}>Approve {selected.length}</Button>
                  <Button size="small" color="error" variant="contained" startIcon={<Close />}
                    onClick={() => setRejectDialog(true)} disabled={actionLoading}>Reject {selected.length}</Button>
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
            pageSizeOptions={[25, 50, 100]} initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            slots={{ toolbar: GridToolbar }} slotProps={{ toolbar: { showQuickFilter: true } }} density="comfortable"
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
            <Button color="error" variant="contained" onClick={() => handleBulkAction("reject", rejectReason)} disabled={actionLoading}>
              Confirm Reject
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </RoleGuard>
  );
}
