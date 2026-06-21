/**
 * FabricShield AI - Scan Page
 * Trigger metadata-only PII/PHI scans against a registered connection.
 */

import React, { useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress,
  Divider, FormControl, FormControlLabel, FormHelperText, InputLabel, LinearProgress,
  ListItemText, MenuItem, OutlinedInput, Select, Stack, Switch, Typography,
} from "@mui/material";
import { PlayArrow, Refresh, Storage, VerifiedUser } from "@mui/icons-material";
import { useMsal } from "@azure/msal-react";
import { useSnackbar } from "notistack";
import { useNavigate } from "react-router-dom";
import { scanApi, connectionsApi } from "../services/api";
import RoleGuard from "../components/RoleGuard";

const STATUS_COLOR = { running: "info", completed: "success", failed: "error" };
const SELECT_ALL = "__select_all__";

export default function Scan() {
  const { accounts } = useMsal();
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const tenantId = accounts[0]?.tenantId || "";

  const [connections, setConnections] = useState([]);
  const [connName, setConnName] = useState("");
  const [schemaOptions, setSchemaOptions] = useState([]);
  const [selectedSchemas, setSelectedSchemas] = useState([]);
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [schemaError, setSchemaError] = useState(null);
  const [contentScan, setContentScan] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [activeScan, setActiveScan] = useState(null);
  const [recentScans, setRecentScans] = useState([]);
  const [loadingScans, setLoadingScans] = useState(true);

  useEffect(() => {
    connectionsApi.list().then((r) => setConnections(r.data)).catch(() => {});
    scanApi.listScans(10).then((r) => setRecentScans(r.data)).catch(() => {}).finally(() => setLoadingScans(false));
  }, []);

  const selectedConn = connections.find((c) => c.name === connName);

  // Load schemas whenever the chosen connection changes.
  const loadSchemas = (name) => {
    if (!name) return;
    const conn = connections.find((c) => c.name === name);
    setLoadingSchemas(true);
    setSchemaError(null);
    setSchemaOptions([]);
    setSelectedSchemas([]);
    connectionsApi
      .schemas(name, conn?.database_type || "azure_sql")
      .then((r) => {
        const opts = r.data || [];
        setSchemaOptions(opts);
        // Pre-select all by default for convenience.
        setSelectedSchemas(opts);
        if (opts.length === 0) setSchemaError("No schemas with tables found on this connection.");
      })
      .catch((err) => setSchemaError(err.message || "Could not load schemas"))
      .finally(() => setLoadingSchemas(false));
  };

  const handleConnChange = (name) => {
    setConnName(name);
    loadSchemas(name);
  };

  const handleSchemaChange = (e) => {
    const value = e.target.value;
    if (value.includes(SELECT_ALL)) {
      setSelectedSchemas(selectedSchemas.length === schemaOptions.length ? [] : schemaOptions);
      return;
    }
    setSelectedSchemas(typeof value === "string" ? value.split(",") : value);
  };

  const allSelected = schemaOptions.length > 0 && selectedSchemas.length === schemaOptions.length;

  useEffect(() => {
    if (!activeScan || activeScan.status !== "running") return;
    const interval = setInterval(() => {
      scanApi.getScan(activeScan.scan_id).then((res) => {
        setActiveScan(res.data);
        if (res.data.status !== "running") {
          setRecentScans((prev) => [res.data, ...prev.filter((s) => s.scan_id !== res.data.scan_id)]);
          if (res.data.status === "completed") {
            enqueueSnackbar(`Scan complete: ${res.data.pii_columns?.length ?? 0} PII columns found`, { variant: "success" });
          } else if (res.data.status === "failed") {
            enqueueSnackbar(`Scan failed: ${res.data.error || "unknown error"}`, { variant: "error" });
          }
        }
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [activeScan, enqueueSnackbar]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const payload = {
        tenant_id: tenantId,
        connection_name: connName,
        database_type: selectedConn?.database_type || "azure_sql",
        schema_names: selectedSchemas,
        content_scan: contentScan,
      };
      const res = await scanApi.triggerScan(payload);
      const initial = { scan_id: res.data.scan_id, status: "running", started_at: new Date().toISOString(), connection_name: connName };
      setActiveScan(initial);
      setRecentScans((prev) => [initial, ...prev]);
      enqueueSnackbar("Scan started", { variant: "info" });
    } catch (err) {
      setError(err.message || "Scan failed to start");
      enqueueSnackbar(err.message || "Scan failed to start", { variant: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <RoleGuard roles={["analyst", "approver", "admin"]}>
      <Box>
        <Typography variant="h4" gutterBottom>Scan Database</Typography>
        <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 3 }}>
          Detect PII and PHI from column metadata - schema, names and types only
        </Typography>

        <Alert icon={<VerifiedUser />} severity="success" variant="outlined" sx={{ mb: 3 }}>
          By default FabricShield reads only column names and data types - never a row of your data.
          Deep content scan (opt-in, below) samples values in memory with consent and never logs or stores them.
        </Alert>

        <Box sx={{ display: "grid", gridTemplateColumns: { md: "1fr 1fr" }, gap: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Configure Scan</Typography>
              {connections.length === 0 ? (
                <Alert severity="warning" sx={{ mt: 1 }}
                  action={<Button color="inherit" size="small" startIcon={<Storage />} onClick={() => navigate("/connections")}>Add</Button>}>
                  No connections registered yet. Add one on the Connections page first.
                </Alert>
              ) : (
                <Box component="form" onSubmit={handleSubmit}>
                  <Stack spacing={2.5}>
                    <FormControl fullWidth required>
                      <InputLabel>Connection</InputLabel>
                      <Select value={connName} label="Connection" onChange={(e) => handleConnChange(e.target.value)}>
                        {connections.map((c) => (
                          <MenuItem key={c.name} value={c.name}>
                            {c.name} - {c.server}/{c.database} ({c.auth_mode === "sql" ? "SQL" : "SP"})
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl fullWidth required disabled={!connName || loadingSchemas || schemaOptions.length === 0}>
                      <InputLabel>Schemas to Scan</InputLabel>
                      <Select
                        multiple
                        value={selectedSchemas}
                        onChange={handleSchemaChange}
                        input={<OutlinedInput label="Schemas to Scan" />}
                        renderValue={(selected) =>
                          allSelected ? "All schemas" : selected.join(", ")
                        }
                        endAdornment={
                          loadingSchemas ? <CircularProgress size={18} sx={{ mr: 3 }} /> : null
                        }
                      >
                        <MenuItem value={SELECT_ALL}>
                          <Checkbox
                            checked={allSelected}
                            indeterminate={selectedSchemas.length > 0 && !allSelected}
                          />
                          <ListItemText primary="Select All" primaryTypographyProps={{ fontWeight: 600 }} />
                        </MenuItem>
                        {schemaOptions.map((s) => (
                          <MenuItem key={s} value={s}>
                            <Checkbox checked={selectedSchemas.indexOf(s) > -1} />
                            <ListItemText primary={s} />
                          </MenuItem>
                        ))}
                      </Select>
                      <FormHelperText>
                        {!connName
                          ? "Choose a connection to load its schemas"
                          : loadingSchemas
                          ? "Loading schemas..."
                          : schemaError
                          ? schemaError
                          : `${selectedSchemas.length} of ${schemaOptions.length} schema(s) selected`}
                        {connName && !loadingSchemas && (
                          <Button size="small" startIcon={<Refresh />} sx={{ ml: 1, minWidth: 0 }}
                            onClick={() => loadSchemas(connName)}>Reload</Button>
                        )}
                      </FormHelperText>
                    </FormControl>

                    <Divider />
                    <Box>
                      <FormControlLabel
                        control={<Switch checked={contentScan} onChange={(e) => setContentScan(e.target.checked)} />}
                        label="Deep content scan (sample values)"
                      />
                      <FormHelperText sx={{ mt: -0.5 }}>
                        Off by default. When on, FabricShield samples column values in memory to
                        detect PII the column names miss (e.g. a card column named &quot;CC&quot;).
                        Values are never logged or stored. Requires data-owner consent.
                      </FormHelperText>
                    </Box>

                    {error && <Alert severity="error">{error}</Alert>}
                    <Button type="submit" variant="contained" size="large"
                      startIcon={submitting ? <CircularProgress size={18} color="inherit" /> : <PlayArrow />}
                      disabled={submitting || !connName || selectedSchemas.length === 0}>
                      {submitting ? "Starting Scan..." : "Start Scan"}
                    </Button>
                  </Stack>
                </Box>
              )}
            </CardContent>
          </Card>

          <Box>
            {activeScan && (
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                    <Typography variant="h6">Active Scan</Typography>
                    <Chip label={activeScan.status} color={STATUS_COLOR[activeScan.status] || "default"} size="small" />
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block">ID: {activeScan.scan_id}</Typography>
                  {activeScan.status === "running" && <LinearProgress sx={{ mt: 1.5 }} />}
                  {activeScan.status === "completed" && (
                    <Alert severity="success" sx={{ mt: 1.5 }}
                      action={<Button color="inherit" size="small" onClick={() => navigate("/approvals")}>Review</Button>}>
                      Found <strong>{activeScan.pii_columns?.length ?? 0}</strong> PII columns.
                    </Alert>
                  )}
                  {activeScan.status === "failed" && <Alert severity="error" sx={{ mt: 1.5 }}>{activeScan.error}</Alert>}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Recent Scans</Typography>
                {loadingScans ? (
                  <CircularProgress size={24} />
                ) : recentScans.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">No scans yet.</Typography>
                ) : (
                  <Stack spacing={1} divider={<Box sx={{ borderBottom: "1px solid", borderColor: "divider" }} />}>
                    {recentScans.slice(0, 8).map((scan) => (
                      <Box key={scan.scan_id} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", py: 0.5 }}>
                        <Box>
                          <Typography variant="body2" fontWeight={600}>{scan.connection_name || "-"}</Typography>
                          <Typography variant="caption" color="text.secondary">{new Date(scan.started_at).toLocaleString()}</Typography>
                        </Box>
                        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                          {scan.status === "completed" && (
                            <Typography variant="caption" color="success.main">{scan.pii_columns?.length ?? 0} PII</Typography>
                          )}
                          <Chip label={scan.status} color={STATUS_COLOR[scan.status] || "default"} size="small" />
                        </Box>
                      </Box>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>
    </RoleGuard>
  );
}
