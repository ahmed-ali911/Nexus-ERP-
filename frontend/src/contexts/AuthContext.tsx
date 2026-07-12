import { createContext, useContext, useState, type ReactNode } from "react";

export interface Permission {
  module: string;
  action: string;
  resource: string;
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  companyId: number;
  roles: string[];
  permissions: string[]; // "module.resource.action" e.g. "sales.invoice.create"
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: AuthUser, token: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );

  const setAuth = (u: AuthUser, t: string) => {
    setUser(u);
    setToken(t);
    localStorage.setItem("access_token", t);
  };

  const clearAuth = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  };

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated: !!token, setAuth, clearAuth }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Returns true if the current user has the given permission string. */
export function useHasPermission(permission: string): boolean {
  const { user } = useAuth();
  if (!user) return false;
  return user.permissions.includes(permission) || user.permissions.includes("*");
}
