/**
 * FabricShield AI - Connections
 * Register and test the SQL servers / databases FabricShield can scan (hybrid auth).
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem, Radio,
  RadioGroup, Select, Stack, TextField, Typography,
} from "@mui/material";
import { Add, Delete, NetworkCheck, Storage } from "@mui/icons-material";
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
  const [testing, setTesting] = useState(null);
  const [form, setForm] = useState(BLANK);

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
      enqueueSnackbar("Connection saved", { variant: "success" });
      setDialog(false); setForm(BLANK); load();
    } catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
    finally { setSaving(false); }
  };

  const test = async (name) => {
    setTesting(name);
    try {
      const r = await connectionsApi.test(name);
      enqueueSnackbar(r.data.success ? `Connected - ${r.data.table_count} tables visible` : `Failed: ${r.data.message}`,
        { variant: r.data.success ? "success" : "error" });
    } catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
    finally { setTesting(null); }
  };

  const remove = async (name) => {
    try { await connectionsApi.remove(name); enqueueSnackbar("Connection deleted", { variant: "info" }); load(); }
    catch (e) { enqueueSnackbar(e.message, { variant: "error" }); }
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
          Service-principal connections use cross-tenant Entra auth with no stored password (recommended). SQL connections store a login and password securely in Key Vault.
        </Alert>

        {loading ? (
          <CircularProgress />
        ) : rows.length === 0 ? (
          <Card><CardContent>
            <Typography color="text.secondary">No connections yet.{canManage ? " Click New Connection to add one." : ""}</Typography>
          </CardContent></Card>
        ) : (
          <Stack spacing={1.5}>
            {rows.map((c) => (
              <Card key={c.name}>
                <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
                  <Storage color="primary" />
                  <Box sx={{ flex: 1, minWidth: 180 }}>
                    <Typography variant="subtitle2" fontWeight={700}>{c.name}</Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>{c.server} / {c.database}</Typography>
                  </Box>
                  <Chip size="small" variant="outlined" label={c.database_type === "fabric" ? "Fabric" : "Azure SQL"} />
                  <Chip size="small" color={c.auth_mode === "sql" ? "warning" : "success"}
                    label={c.auth_mode === "sql" ? "SQL auth" : "Service principal"} />
                  <Button size="small" onClick={() => test(c.name)} disabled={testing === c.name}
                    startIcon={testing === c.name ? <CircularProgress size={14} /> : <NetworkCheck />}>Test</Button>
                  {canManage && <Button size="small" color="error" startIcon={<Delete />} onClick={() => remove(c.name)}>Delete</Button>}
                </CardContent>
              </Card>
            ))}
          </Stack>
        )}

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
      </Box>
    </RoleGuard>
  );
}
