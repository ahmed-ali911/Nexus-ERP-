import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  children: ReactNode;
  /** Optional specific permission required to access this route. */
  permission?: string;
}

/**
 * Wraps protected routes. Redirects to /login when not authenticated.
 * When `permission` is specified, redirects to /403 if the user lacks it.
 *
 * NOTE: In DEV mode, auth check is bypassed so the demo is accessible
 * without a real login flow. Remove this bypass before production.
 */
export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();

  // DEV bypass: skip auth in development so demo pages are accessible
  if (import.meta.env.DEV && !isAuthenticated) {
    console.warn("[ProtectedRoute] DEV mode: bypassing auth check");
    return <>{children}</>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (permission && user && !user.permissions.includes(permission) && !user.permissions.includes("*")) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
