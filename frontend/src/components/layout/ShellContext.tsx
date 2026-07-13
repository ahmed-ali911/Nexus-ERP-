import { createContext, useContext, useState, type ReactNode } from "react";

export interface ShellContextValue {
  collapsed: boolean;
  setCollapsed: (c: boolean) => void;
  toggleCollapsed: () => void;
  mobileOpen: boolean;
  setMobileOpen: (o: boolean) => void;
}

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <ShellContext.Provider
      value={{
        collapsed,
        setCollapsed,
        toggleCollapsed: () => setCollapsed((c) => !c),
        mobileOpen,
        setMobileOpen,
      }}
    >
      {children}
    </ShellContext.Provider>
  );
}

export function useShell(): ShellContextValue {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used inside ShellProvider");
  return ctx;
}
