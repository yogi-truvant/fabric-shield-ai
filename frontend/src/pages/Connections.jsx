/**
 * FabricShield AI - Connections
 * Register data sources, then Connect → (Test / Refresh / Delete). Hybrid auth.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem, Radio,
  RadioGroup, Select, Stack, TextField, Typography,
} from "@mui/material";
import { Add, CheckCircle, Delete, LinkOff, NetworkCheck, Power, Refresh, Storage } from "@mui/icons-material";
import { useMsal } from "@azure/msal-react";
import { useSnackbar } from "notistack";
import { connectionsApi } from "../services/api";
import RoleGuard from "../components/RoleGuard";
import { useRole } from "../hooks/useRole";

const BLANK = { name: "", server: "", database: "", database_type: "azure_sql", auth_mode: "service_principal", sql_username: "", sql_password: "" };

export default function Connections() {
  const { accounts } = useMsal();
  const { hasRole } = useRole();
  const { enqueueSnackbar } = useSnackbar();
  const tenantId = accounts[0]?.tenantId || "";
  const canManage = hasRole("admin");

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(null);           // connection name currently testing/connecting
  const [connected, setConnected] = useState({});   // name -> true once verified this session
  const [form, setForm] = useState(BLANK);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    connectionsApi.list().then((r) => setRows(r.data))
      .catch((e) => enqueueSnackbar(e.message, { variant: "error" }))
      .finally(() => setLoading(false));
  }, [enqueueSnackbar]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    setSaving(true);
    try {
      await connectionsApi.create({ ...form, tenant_id: tenantId });
      enqueueSnackbar("Connection saved - click Connect to verify it", { variant: "success" });
      setDialog(false); setForm(BLANK); load();
    } catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
    finally { setSaving(false); }
  };

  // Connect / Test both run the metadata-only reachability check.
  const verify = async (c, { connecting } = {}) => {
    setBusy(c.name);
    try {
      const r = await connectionsApi.test(c.name, c.database_type);
      if (r.data.success) {
        setConnected((m) => ({ ...m, [c.name]: true }));
        enqueueSnackbar(`${connecting ? "Connected" : "Connection OK"} - ${r.data.table_count} tables visible`, { variant: "success" });
      } else {
        setConnected((m) => ({ ...m, [c.name]: false }));
        enqueueSnackbar(`Failed: ${r.data.message}`, { variant: "error" });
      }
    } catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
    finally { setBusy(null); }
  };

  const disconnect = (name) => {
    setConnected((m) => { const n = { ...m }; delete n[name]; return n; });
    enqueueSnackbar(`Disconnected ${name}`, { variant: "info" });
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      const r = await connectionsApi.remove(deleteTarget.name);
      const d = r.data || {};
      enqueueSnackbar(
        `Connection deleted - cleared ${d.approvals_removed ?? 0} approval(s) and ${d.scans_removed ?? 0} scan(s)`,
        { variant: "info" });
      setConnected((m) => { const n = { ...m }; delete n[deleteTarget.name]; return n; });
      load();
    } catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
    finally { setDeleting(false); setDeleteTarget(null); }
  };

  return (
    <RoleGuard roles={["analyst", "approver", "admin"]}>
      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Box>
            <Typography variant="h4">Connections</Typography>
            <Typography variant="subtitle1" color="text.secondary">Register the SQL servers and databases FabricShield can scan</Typography>
          </Box>
          {canManage && <Button variant="contained" startIcon={<Add />} onClick={() => setDialog(true)}>New Connection</Button>}
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          Save a connection, then <strong>Connect</strong> to verify it. Service-principal uses cross-tenant Entra auth (no stored password); SQL stores a login + password securely in Key Vault.
        </Alert>

        {loading ? (
          <CircularProgress />
        ) : rows.length === 0 ? (
          <Card><CardContent>
            <Typography color="text.secondary">No connections yet.{canManage ? " Click New Connection to add one." : ""}</Typography>
          </CardContent></Card>
        ) : (
          <Stack spacing={1.5}>
            {rows.map((c) => {
              const isConnected = !!connected[c.name];
              const isBusy = busy === c.name;
              return (
                <Card key={c.name}>
                  <CardContent sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1.5, rowGap: 1.5 }}>
                    {/* Identity (grows/shrinks, truncates — never forces horizontal scroll) */}
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flex: "1 1 240px", minWidth: 0 }}>
                      <Storage color="primary" />
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="subtitle2" fontWeight={700} noWrap>{c.name}</Typography>
                        <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
                          {c.server} / {c.database}
                        </Typography>
                      </Box>
                    </Box>
                    {/* Chips + actions: this group wraps below on narrow screens */}
                    <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, justifyContent: "flex-end" }}>
                      <Chip size="small" variant="outlined" label={c.database_type === "fabric" ? "Fabric" : "Azure SQL"} />
                      <Chip size="small" color={c.auth_mode === "sql" ? "warning" : "success"}
                        label={c.auth_mode === "sql" ? "SQL auth" : "Service principal"} />
                      <Chip size="small" icon={isConnected ? <CheckCircle /> : <LinkOff />}
                        color={isConnected ? "success" : "default"} variant={isConnected ? "filled" : "outlined"}
                        label={isConnected ? "Connected" : "Not connected"} />

                      {!isConnected ? (
                        <Button size="small" variant="contained" onClick={() => verify(c, { connecting: true })} disabled={isBusy}
                          startIcon={isBusy ? <CircularProgress size={14} color="inherit" /> : <Power />}>Connect</Button>
                      ) : (
                        <>
                          <Button size="small" onClick={() => verify(c)} disabled={isBusy}
                            startIcon={isBusy ? <CircularProgress size={14} /> : <NetworkCheck />}>Test</Button>
                          <Button size="small" onClick={load} startIcon={<Refresh />}>Refresh</Button>
                          <Button size="small" color="inherit" onClick={() => disconnect(c.name)}
                            startIcon={<LinkOff />}>Disconnect</Button>
                        </>
                      )}
                      {canManage && (
                        <Button size="small" color="error" startIcon={<Delete />} onClick={() => setDeleteTarget(c)}>Delete</Button>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              );
            })}
          </Stack>
        )}

        {/* New connection dialog */}
        <Dialog open={dialog} onClose={() => setDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle>New Connection</DialogTitle>
          <DialogContent>
            <Stack spacing={2.5} sx={{ mt: 1 }}>
              <TextField label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                helperText="Letters, numbers, dashes (e.g. aqueducts-prod)" />
              <TextField label="Server" required value={form.server} onChange={(e) => setForm({ ...form, server: e.target.value })}
                helperText="e.g. aqctest.database.windows.net" />
              <TextField label="Database" required value={form.database} onChange={(e) => setForm({ ...form, database: e.target.value })} />
              <FormControl fullWidth>
                <InputLabel>Database Type</InputLabel>
                <Select value={form.database_type} label="Database Type" onChange={(e) => setForm({ ...form, database_type: e.target.value })}>
                  <MenuItem value="azure_sql">Azure SQL Database</MenuItem>
                  <MenuItem value="fabric">Microsoft Fabric (SQL Endpoint)</MenuItem>
                </Select>
              </FormControl>
              <FormControl>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>Authentication</Typography>
                <RadioGroup value={form.auth_mode} onChange={(e) => setForm({ ...form, auth_mode: e.target.value })}>
                  <FormControlLabel value="service_principal" control={<Radio />} label="Service principal (no stored password - recommended)" />
                  <FormControlLabel value="sql" control={<Radio />} label="SQL login and password" />
                </RadioGroup>
              </FormControl>
              {form.auth_mode === "sql" && (
                <>
                  <TextField label="SQL Username" value={form.sql_username} onChange={(e) => setForm({ ...form, sql_username: e.target.value })} />
                  <TextField label="SQL Password" type="password" value={form.sql_password} onChange={(e) => setForm({ ...form, sql_password: e.target.value })} />
                </>
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialog(false)}>Cancel</Button>
            <Button variant="contained" onClick={create}
              disabled={saving || !form.name || !form.server || !form.database || (form.auth_mode === "sql" && (!form.sql_username || !form.sql_password))}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete confirmation */}
        <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
          <DialogTitle>Delete connection?</DialogTitle>
          <DialogContent>
            <Typography variant="body2">
              Delete <strong>{deleteTarget?.name}</strong>? This removes the connection for everyone in your
              organization and clears its scan results and approvals (the dashboard resets). The audit log is
              kept. Masks already applied in the database are <strong>not</strong> removed. This cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button color="error" variant="contained" onClick={confirmDelete} disabled={deleting}
              startIcon={deleting ? <CircularProgress size={14} color="inherit" /> : <Delete />}>
              Delete connection
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </RoleGuard>
  );
}
