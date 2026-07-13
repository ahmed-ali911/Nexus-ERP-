import { createContext, useContext, useState, type ReactNode } from "react";

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  companyId: number;
  fullNameEn: string;
  fullNameAr: string;
  isSuperuser: boolean;
  roles: string[];
  /** Permission codes; superusers get ["*"], others get their explicit codes. */
  permissions: string[];
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: AuthUser, accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem("auth_user");
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(loadStoredUser);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );

  const setAuth = (u: AuthUser, accessToken: string, refreshToken: string) => {
    setUser(u);
    setToken(accessToken);
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    localStorage.setItem("auth_user", JSON.stringify(u));
  };

  const clearAuth = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("auth_user");
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
