import type { ReactNode } from "react";
import { useHasPermission } from "@/contexts/AuthContext";

interface CanProps {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Renders children only when the current user has the given permission.
 * Use for hiding UI elements the user isn't allowed to interact with.
 *
 * Usage:  <Can permission="sales.invoice.create"><AppButton>New Invoice</AppButton></Can>
 */
export function Can({ permission, children, fallback = null }: CanProps) {
  const allowed = useHasPermission(permission);
  return <>{allowed ? children : fallback}</>;
}
