import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  children: ReactNode;
  /** Optional permission code required to access this route. */
  permission?: string;
}

/** Redirects unauthenticated users to /login; redirects to /403 for missing permission. */
export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (
    permission &&
    user &&
    !user.permissions.includes(permission) &&
    !user.permissions.includes("*")
  ) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
