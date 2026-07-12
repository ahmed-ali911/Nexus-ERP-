import { createContext, useContext, useState, type ReactNode } from "react";

interface OrgScope {
  companyId: number | null;
  branchId: number | null;
  warehouseId: number | null;
}

interface OrgContextValue {
  scope: OrgScope;
  setScope: (scope: Partial<OrgScope>) => void;
}

const OrgContext = createContext<OrgContextValue | null>(null);

export function OrgProvider({ children }: { children: ReactNode }) {
  const [scope, setScope] = useState<OrgScope>({
    companyId: null,
    branchId: null,
    warehouseId: null,
  });

  const update = (partial: Partial<OrgScope>) =>
    setScope((prev) => ({ ...prev, ...partial }));

  return (
    <OrgContext.Provider value={{ scope, setScope: update }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrgScope(): OrgContextValue {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrgScope must be used inside OrgProvider");
  return ctx;
}
