/**
 * FabricShield AI - Dashboard
 * Centered KPI cards (clickable) + native interactive charts.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Box, Button, Card, CardContent, Grid, LinearProgress, Skeleton, Typography,
} from "@mui/material";
import { CheckCircle, Error as ErrorIcon, Refresh, TableChart, Timer } from "@mui/icons-material";
import { useNavigate } from "react-router-dom";
import {
  PieChart, Pie, Cell, Tooltip as ReTooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { approvalsApi } from "../services/api";

const PIE_COLORS = ["#0078d4", "#d13438", "#ff8c00", "#107c10", "#5c2d91", "#008272", "#e3008c", "#605e5c"];

function KpiCard({ title, value, subtitle, icon, color = "primary.main", loading, onClick }) {
  return (
    <Card onClick={onClick} sx={{
      height: "100%", cursor: onClick ? "pointer" : "default",
      transition: "box-shadow .2s ease, transform .2s ease",
      "&:hover": onClick ? { boxShadow: 6, transform: "translateY(-3px)" } : {},
    }}>
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <Box>
            <Typography variant="subtitle1" color="text.secondary">{title}</Typography>
            {loading ? <Skeleton width={80} height={40} />
              : <Typography variant="h4" fontWeight={700} color={color}>{value ?? "0"}</Typography>}
            {subtitle && <Typography variant="caption" color="text.secondary">{subtitle}</Typography>}
          </Box>
          <Box sx={{ color, opacity: 0.7, mt: 0.5 }}>{icon}</Box>
        </Box>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [dist, setDist] = useState([]);
  const [byTable, setByTable] = useState([]);

  const load = useCallback(() => {
    setStatsLoading(true);
    approvalsApi.getStats().then((r) => setStats(r.data)).catch(() => setStats(null)).finally(() => setStatsLoading(false));
    approvalsApi.listApprovals({ limit: 500 }).then((r) => {
      const ent = {}, tbl = {};
      (r.data || []).forEach((a) => {
        ent[a.entity_type] = (ent[a.entity_type] || 0) + 1;
        const key = `${a.schema_name}.${a.table_name}`;
        tbl[key] = (tbl[key] || 0) + 1;
      });
      setDist(Object.entries(ent).map(([name, value]) => ({ name, value })));
      setByTable(Object.entries(tbl).map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value).slice(0, 6));
    }).catch(() => { setDist([]); setByTable([]); });
  }, []);

  useEffect(() => { load(); }, [load]);

  const hasData = dist.length > 0;

  return (
    <Box>
      <Box sx={{ textAlign: "center", mb: 3 }}>
        <Typography variant="h4" gutterBottom>Governance Dashboard</Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Real-time PII / PHI compliance overview for your data estate
        </Typography>
        <Button size="small" startIcon={<Refresh />} onClick={load} sx={{ mt: 1 }}>Refresh</Button>
      </Box>

      <Grid container spacing={2} sx={{ mb: 3 }} justifyContent="center">
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Total PII Columns" value={stats?.total_pii_columns}
            icon={<TableChart sx={{ fontSize: 32 }} />} loading={statsLoading} onClick={() => navigate("/approvals")} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="High Risk (Pending)" value={stats ? `${stats.high_risk_pct}%` : null}
            subtitle={`${stats?.pending ?? 0} columns awaiting approval`} icon={<ErrorIcon sx={{ fontSize: 32 }} />}
            color="error.main" loading={statsLoading} onClick={() => navigate("/approvals")} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Masking Coverage" value={stats ? `${stats.masking_coverage_pct}%` : null}
            subtitle={`${stats?.masked ?? 0} columns masked`} icon={<CheckCircle sx={{ fontSize: 32 }} />}
            color="success.main" loading={statsLoading} onClick={() => navigate("/approvals")} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Pending Approvals" value={stats?.pending}
            icon={<Timer sx={{ fontSize: 32 }} />} color="warning.main" loading={statsLoading} onClick={() => navigate("/approvals")} />
        </Grid>
      </Grid>

      {stats && stats.total_pii_columns > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
              <Typography variant="body2" fontWeight={600}>Masking Coverage Progress</Typography>
              <Typography variant="body2" color="success.main" fontWeight={700}>{stats.masking_coverage_pct}%</Typography>
            </Box>
            <LinearProgress variant="determinate" value={stats.masking_coverage_pct}
              color={stats.masking_coverage_pct >= 80 ? "success" : "warning"} sx={{ height: 8, borderRadius: 4 }} />
            <Box sx={{ display: "flex", justifyContent: "space-between", mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">{stats.masked} / {stats.total_pii_columns} columns protected</Typography>
              <Typography variant="caption" color="error.main">{stats.pending} pending review</Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {hasData ? (
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>PII / PHI Distribution by Type</Typography>
                <Box sx={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={dist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={105}
                        label={(d) => `${d.name} (${d.value})`}>
                        {dist.map((e, i) => <Cell key={e.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <ReTooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>Top Tables by PII Count</Typography>
                <Box sx={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={byTable} layout="vertical" margin={{ left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                      <ReTooltip />
                      <Bar dataKey="value" fill="#0078d4" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: "center", py: 6 }}>
              <Typography variant="h6" gutterBottom>No PII columns detected yet</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Run a metadata scan to populate your governance dashboard.
              </Typography>
              <Button variant="contained" startIcon={<TableChart />} onClick={() => navigate("/scan")}>
                Run your first scan
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
