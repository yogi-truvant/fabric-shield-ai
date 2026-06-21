/**
 * FabricShield AI - Error Boundary
 * Catches render-time JS errors anywhere below it and shows a friendly fallback
 * instead of a blank white screen. React error boundaries must be class components.
 */

import React from "react";
import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { ErrorOutline, Refresh } from "@mui/icons-material";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Surface to the console (and any attached telemetry) without leaking to the UI.
    console.error("[FabricShield] Unhandled UI error:", error, info?.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "60vh", p: 3 }}>
        <Card sx={{ maxWidth: 460, width: "100%" }}>
          <CardContent>
            <Stack spacing={2} alignItems="center" textAlign="center">
              <ErrorOutline color="error" sx={{ fontSize: 48 }} />
              <Typography variant="h6">Something went wrong</Typography>
              <Typography variant="body2" color="text.secondary">
                The page hit an unexpected error. Your data is safe - FabricShield only ever reads
                column metadata. Try again, or return to the dashboard.
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button variant="contained" startIcon={<Refresh />} onClick={() => window.location.assign("/")}>
                  Back to Dashboard
                </Button>
                <Button variant="outlined" onClick={this.handleReset}>Try Again</Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      </Box>
    );
  }
}
