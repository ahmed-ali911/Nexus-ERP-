import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export interface ShellContextValue {
  collapsed: boolean;
  setCollapsed: (c: boolean) => void;
  toggleCollapsed: () => void;
  mobileOpen: boolean;
  setMobileOpen: (o: boolean) => void;
  isSectionExpanded: (key: string) => boolean;
  toggleSection: (key: string) => void;
  expandSection: (key: string) => void;
}

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  // Store collapsed (closed) sections — empty set = all expanded by default
  const [collapsedSections, setCollapsedSections] = useState<ReadonlySet<string>>(new Set());

  const isSectionExpanded = useCallback(
    (key: string) => !collapsedSections.has(key),
    [collapsedSections],
  );

  const toggleSection = useCallback((key: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const expandSection = useCallback((key: string) => {
    setCollapsedSections((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }, []);

  return (
    <ShellContext.Provider
      value={{
        collapsed,
        setCollapsed,
        toggleCollapsed: () => setCollapsed((c) => !c),
        mobileOpen,
        setMobileOpen,
        isSectionExpanded,
        toggleSection,
        expandSection,
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
