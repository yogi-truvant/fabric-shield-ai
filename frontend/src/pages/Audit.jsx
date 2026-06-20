/**
 * FabricShield AI - Audit Log Page
 * Immutable, searchable audit trail for compliance reporting.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem,
  Select, Typography,
} from "@mui/material";
import { Download, Refresh } from "@mui/icons-material";
import { DataGrid, GridToolbar } from "@mui/x-data-grid";
import { auditApi } from "../services/api";
import RoleGuard from "../components/RoleGuard";

const ACTION_GROUPS = {
  "scan.started": { color: "info", group: "Scan" },
  "scan.completed": { color: "success", group: "Scan" },
  "scan.failed": { color: "error", group: "Scan" },
  "approval.submitted": { color: "info", group: "Approval" },
  "masking.applied": { color: "success", group: "Masking" },
  "masking.failed": { color: "error", group: "Masking" },
  "purview.classification_pushed": { color: "secondary", group: "Governance" },
  "marketplace.tenant_provisioned": { color: "primary", group: "Platform" },
};

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    auditApi.getLogs({ action: actionFilter || undefined, limit: 200 })
      .then((res) => setRows(res.data.logs.map((l) => ({ ...l, id: l.log_id }))))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [actionFilter]);

  useEffect(() => { load(); }, [load]);

  const columns = [
    {
      field: "timestamp", headerName: "Timestamp", width: 180,
      valueFormatter: (v) => v ? new Date(v).toLocaleString() : "-",
    },
    {
      field: "action", headerName: "Action", width: 220,
      renderCell: (params) => {
        const cfg = ACTION_GROUPS[params.value] || { color: "default" };
        return <Chip size="small" label={params.value} color={cfg.color} variant="outlined" />;
      },
    },
    { field: "actor_email", headerName: "Actor", width: 200, flex: 1 },
    { field: "resource_id", headerName: "Resource ID", width: 180 },
    {
      field: "success", headerName: "Result", width: 90,
      renderCell: (params) => (
        <Chip size="small" label={params.value ? "Success" : "Failed"} color={params.value ? "success" : "error"} />
      ),
    },
    {
      field: "error_message", headerName: "Error", width: 200,
      renderCell: (params) => params.value ? (
        <Typography variant="caption" color="error.main">{params.value}</Typography>
      ) : null,
    },
  ];

  const exportCsv = () => {
    const headers = "timestamp,action,actor_email,resource_id,success,error\n";
    const body = rows.map((r) =>
      `"${r.timestamp}","${r.action}","${r.actor_email || ""}","${r.resource_id || ""}","${r.success}","${r.error_message || ""}"`
    ).join("\n");
    const blob = new Blob([headers + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fabricshield-audit-${Date.now()}.csv`;
    a.click();
  };

  return (
    <RoleGuard roles={["analyst", "approver", "admin"]}>
      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Box>
            <Typography variant="h4">Audit Log</Typography>
            <Typography variant="subtitle1">Immutable record of all governance actions</Typography>
          </Box>
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button startIcon={<Download />} onClick={exportCsv} variant="outlined" size="small">
              Export CSV
            </Button>
            <Button startIcon={<Refresh />} onClick={load} variant="outlined" size="small">
              Refresh
            </Button>
          </Box>
        </Box>

        {/* Filter */}
        <Box sx={{ mb: 2, maxWidth: 300 }}>
          <FormControl fullWidth size="small">
            <InputLabel>Filter by Action</InputLabel>
            <Select
              value={actionFilter}
              label="Filter by Action"
              onChange={(e) => setActionFilter(e.target.value)}
            >
              <MenuItem value="">All Actions</MenuItem>
              {Object.keys(ACTION_GROUPS).map((a) => (
                <MenuItem key={a} value={a}>{a}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          Audit records are immutable and append-only. Records cannot be modified or deleted.
        </Alert>

        <Box sx={{ height: 600, width: "100%" }}>
          <DataGrid
            rows={rows}
            columns={columns}
            loading={loading}
            pageSizeOptions={[25, 50, 100]}
            initialState={{ pagination: { paginationModel: { pageSize: 50 } } }}
            slots={{ toolbar: GridToolbar }}
            slotProps={{ toolbar: { showQuickFilter: true } }}
            density="compact"
            disableRowSelectionOnClick
          />
        </Box>
      </Box>
    </RoleGuard>
  );
}
