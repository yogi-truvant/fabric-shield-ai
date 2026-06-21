/**
 * FabricShield AI - App Shell Layout
 * Top AppBar (with theme toggle) + role-aware sidebar + footer.
 */

import React, { useContext, useState } from "react";
import {
  AppBar, Avatar, Box, Chip, Divider, Drawer, IconButton, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, Menu, MenuItem, Toolbar, Tooltip, Typography,
} from "@mui/material";
import {
  Approval, Brightness4, Brightness7, Dashboard, HelpOutline, Logout, Menu as MenuIcon,
  Security, Shield, Storage, TableChart, VerifiedUser,
} from "@mui/icons-material";
import { useNavigate, useLocation } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useRole } from "../hooks/useRole";
import { ColorModeContext } from "../colorMode";

const DRAWER_WIDTH = 240;
const APP_VERSION = "1.0.0";

const navItems = [
  { label: "Dashboard", path: "/", icon: <Dashboard />, roles: ["viewer", "analyst", "approver", "admin"] },
  { label: "Scan", path: "/scan", icon: <TableChart />, roles: ["analyst", "approver", "admin"] },
  { label: "Connections", path: "/connections", icon: <Storage />, roles: ["analyst", "approver", "admin"] },
  { label: "Approvals", path: "/approvals", icon: <Approval />, roles: ["analyst", "approver", "admin"] },
  { label: "Audit Log", path: "/audit", icon: <Security />, roles: ["analyst", "approver", "admin"] },
  { label: "Guide", path: "/guide", icon: <HelpOutline />, roles: ["viewer", "analyst", "approver", "admin"] },
];

const ROLE_COLORS = { admin: "error", approver: "warning", analyst: "info", viewer: "default" };

export default function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { instance, accounts } = useMsal();
  const { hasRole, highestRole } = useRole();
  const colorMode = useContext(ColorModeContext);

  const user = accounts[0] || {};
  const displayName = user.name || user.username || "User";
  const initial = displayName.charAt(0).toUpperCase();

  const handleLogout = () => {
    setAnchorEl(null);
    instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin });
  };

  const drawerContent = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box onClick={() => { navigate("/"); setMobileOpen(false); }}
        sx={{ p: 2, display: "flex", alignItems: "center", gap: 1, cursor: "pointer", "&:hover": { bgcolor: "action.hover" } }}>
        <Shield sx={{ color: "primary.main", fontSize: 28 }} />
        <Box>
          <Typography variant="h6" sx={{ lineHeight: 1.2 }}>FabricShield</Typography>
          <Typography variant="caption" color="text.secondary">AI Governance</Typography>
        </Box>
      </Box>
      <Divider />

      <List sx={{ flex: 1, pt: 1 }}>
        {navItems
          .filter((item) => item.roles.some((r) => hasRole(r)))
          .map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => { navigate(item.path); setMobileOpen(false); }}
                sx={{
                  borderRadius: 1.5, mx: 1, my: 0.25,
                  "&.Mui-selected": {
                    backgroundColor: "primary.main", color: "white",
                    "& .MuiListItemIcon-root": { color: "white" },
                    "&:hover": { backgroundColor: "primary.dark" },
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: "0.875rem" }} />
              </ListItemButton>
            </ListItem>
          ))}
      </List>

      <Box sx={{ px: 2, py: 1 }}>
        <Chip
          icon={<VerifiedUser sx={{ fontSize: 16 }} />}
          label="Metadata-only - no row data read"
          size="small" variant="outlined" color="success"
          sx={{ width: "100%", justifyContent: "flex-start", fontSize: "0.68rem" }}
        />
      </Box>
      <Divider />

      <Box sx={{ p: 1.5, pb: 3 }}>
        <ListItemButton onClick={(e) => setAnchorEl(e.currentTarget)} sx={{ borderRadius: 1.5, alignItems: "center", gap: 1.25 }}>
          <Avatar sx={{ width: 34, height: 34, bgcolor: "primary.main", fontSize: 15 }}>{initial}</Avatar>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="body2" noWrap fontWeight={600}>{displayName}</Typography>
            <Chip size="small" label={highestRole} color={ROLE_COLORS[highestRole] || "default"} sx={{ mt: 0.25, height: 18, fontSize: "0.65rem" }} />
          </Box>
        </ListItemButton>
        <Menu
          anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}
          anchorOrigin={{ vertical: "top", horizontal: "center" }}
          transformOrigin={{ vertical: "bottom", horizontal: "center" }}
        >
          <Box sx={{ px: 2, py: 1 }}>
            <Typography variant="body2" fontWeight={600}>{displayName}</Typography>
            <Typography variant="caption" color="text.secondary">{user.username}</Typography>
          </Box>
          <Divider />
          <MenuItem onClick={handleLogout}><Logout fontSize="small" style={{ marginRight: 8 }} /> Sign out</MenuItem>
        </Menu>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar position="fixed" elevation={1} sx={{ zIndex: (t) => t.zIndex.drawer + 1, backgroundColor: "primary.dark" }}>
        <Toolbar variant="dense">
          <IconButton color="inherit" edge="start" onClick={() => setMobileOpen(!mobileOpen)} sx={{ mr: 1, display: { sm: "none" } }}>
            <MenuIcon />
          </IconButton>
          <Shield sx={{ mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>FabricShield AI</Typography>
          <Tooltip title="Connected tenant">
            <Typography variant="caption" sx={{ mr: 1, opacity: 0.85 }}>Tenant {user.tenantId?.slice(0, 8) || "n/a"}</Typography>
          </Tooltip>
          <Tooltip title={colorMode.mode === "dark" ? "Light mode" : "Dark mode"}>
            <IconButton color="inherit" size="small" onClick={colorMode.toggle} sx={{ mr: 0.5 }}>
              {colorMode.mode === "dark" ? <Brightness7 /> : <Brightness4 />}
            </IconButton>
          </Tooltip>
          <Tooltip title="Sign out">
            <IconButton color="inherit" onClick={handleLogout} size="small"><Logout /></IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{ width: DRAWER_WIDTH, flexShrink: 0, display: { xs: "none", sm: "block" },
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", top: "48px", height: "calc(100% - 48px)" } }}
      >
        {drawerContent}
      </Drawer>
      <Drawer
        variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)}
        sx={{ display: { xs: "block", sm: "none" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH } }}
      >
        {drawerContent}
      </Drawer>

      <Box component="main" sx={{
        flexGrow: 1, p: 3, mt: "48px",
        backgroundColor: "background.default", minHeight: "calc(100vh - 48px)",
        display: "flex", flexDirection: "column", alignItems: "center",
      }}>
        <Box sx={{ width: "100%", maxWidth: 1200, flex: 1 }}>{children}</Box>
        <Box sx={{ width: "100%", maxWidth: 1200, mt: 4, pt: 2, borderTop: "1px solid", borderColor: "divider", textAlign: "center" }}>
          <Typography variant="caption" color="text.secondary">
            FabricShield AI v{APP_VERSION} · Secured by Azure Entra ID · Metadata-only governance
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
