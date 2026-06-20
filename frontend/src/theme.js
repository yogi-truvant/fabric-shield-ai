/**
 * FabricShield AI - Material UI Theme (light/dark factory)
 * Primary font: Calibri (falls back to Carlito / Segoe UI on non-Windows).
 */

import { createTheme } from "@mui/material/styles";

const FONT_STACK = '"Calibri", "Carlito", "Segoe UI", "Helvetica Neue", Arial, sans-serif';

const HEADINGS = {
  h1: { fontSize: "2rem", fontWeight: 700 },
  h2: { fontSize: "1.75rem", fontWeight: 600 },
  h3: { fontSize: "1.5rem", fontWeight: 600 },
  h4: { fontSize: "1.25rem", fontWeight: 700 },
  h5: { fontSize: "1.125rem", fontWeight: 600 },
  h6: { fontSize: "1rem", fontWeight: 600 },
  subtitle1: { fontSize: "0.875rem" },
  body1: { fontSize: "0.875rem" },
  body2: { fontSize: "0.8125rem" },
};

export function getTheme(mode = "light") {
  const dark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: { main: "#0078d4", light: "#2b88d8", dark: "#005a9e", contrastText: "#ffffff" },
      secondary: { main: "#107c10", contrastText: "#ffffff" },
      error: { main: "#d13438" },
      warning: { main: "#ff8c00" },
      info: { main: "#0078d4" },
      success: { main: "#107c10" },
      background: dark ? { default: "#1b1a19", paper: "#252423" } : { default: "#f3f2f1", paper: "#ffffff" },
      text: dark ? { primary: "#f3f2f1", secondary: "#c8c6c4" } : { primary: "#323130", secondary: "#605e5c" },
      divider: dark ? "#3b3a39" : "#edebe9",
    },
    typography: { fontFamily: FONT_STACK, ...HEADINGS },
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: { styleOverrides: { body: { fontFamily: FONT_STACK } } },
      MuiButton: {
        styleOverrides: {
          root: { textTransform: "none", fontWeight: 600, fontFamily: FONT_STACK },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            boxShadow: dark
              ? "0 2px 8px rgba(0,0,0,.5)"
              : "0 1.6px 3.6px 0 rgba(0,0,0,.13), 0 0.3px 0.9px 0 rgba(0,0,0,.11)",
            borderRadius: 10,
          },
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: {
            border: `1px solid ${dark ? "#3b3a39" : "#edebe9"}`,
            fontFamily: FONT_STACK,
            "& .MuiDataGrid-columnHeaders": {
              backgroundColor: dark ? "#2d2c2b" : "#faf9f8",
            },
            "& .MuiDataGrid-row:hover": { backgroundColor: dark ? "#2d2c2b" : "#f3f2f1" },
          },
        },
      },
      MuiChip: { styleOverrides: { root: { fontWeight: 600, fontSize: "0.75rem" } } },
    },
  });
}

export const theme = getTheme("light");
