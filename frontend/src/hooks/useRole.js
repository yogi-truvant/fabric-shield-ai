/**
 * FabricShield AI - RBAC Hook
 * Extracts app roles from the MSAL ID token claims.
 */

import { useMemo } from "react";
import { useMsal } from "@azure/msal-react";

const ROLE_HIERARCHY = { viewer: 0, analyst: 1, approver: 2, admin: 3 };

export function useRole() {
  const { accounts } = useMsal();

  const roles = useMemo(() => {
    if (!accounts.length) return [];
    const idTokenClaims = accounts[0].idTokenClaims || {};
    const rawRoles = (idTokenClaims.roles || []).map((r) => r.toLowerCase());
    return rawRoles.length ? rawRoles : ["viewer"];
  }, [accounts]);

  const hasRole = (...requiredRoles) =>
    requiredRoles.some((r) => roles.includes(r.toLowerCase()));

  const highestRole = useMemo(() => {
    if (!roles.length) return "viewer";
    return roles.reduce((best, r) =>
      (ROLE_HIERARCHY[r] ?? -1) > (ROLE_HIERARCHY[best] ?? -1) ? r : best
    , "viewer");
  }, [roles]);

  return { roles, hasRole, highestRole };
}
