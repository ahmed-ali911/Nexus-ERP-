import { createContext, useContext, useState, type ReactNode } from "react";

export interface Company {
  id: number;
  nameEn: string;
  nameAr: string;
}

export interface Branch {
  id: number;
  companyId: number;
  nameEn: string;
  nameAr: string;
}

interface OrgScope {
  companyId: number | null;
  branchId: number | null;
  warehouseId: number | null;
}

// Stub data matching Sham Land seed — replaced by real API call after Login is built
const STUB_COMPANIES: Company[] = [
  { id: 1, nameEn: "Sham Land Trading", nameAr: "شام لاند للتجارة" },
];

const STUB_BRANCHES: Branch[] = [
  { id: 1, companyId: 1, nameEn: "Qurain Branch",    nameAr: "فرع قرين" },
  { id: 2, companyId: 1, nameEn: "Shuwaikh Branch",  nameAr: "فرع الشويخ" },
];

interface OrgContextValue {
  scope: OrgScope;
  setScope: (scope: Partial<OrgScope>) => void;
  companies: Company[];
  branches: Branch[];
  activeCompany: Company | null;
  activeBranch: Branch | null;
  setActiveCompanyId: (id: number) => void;
  setActiveBranchId: (id: number) => void;
}

const OrgContext = createContext<OrgContextValue | null>(null);

export function OrgProvider({ children }: { children: ReactNode }) {
  const [scope, setScopeState] = useState<OrgScope>({
    companyId: STUB_COMPANIES[0]?.id ?? null,
    branchId:  STUB_BRANCHES[0]?.id  ?? null,
    warehouseId: null,
  });

  const setScope = (partial: Partial<OrgScope>) =>
    setScopeState((prev) => ({ ...prev, ...partial }));

  const setActiveCompanyId = (id: number) => {
    const firstBranch = STUB_BRANCHES.find((b) => b.companyId === id);
    setScope({ companyId: id, branchId: firstBranch?.id ?? null });
  };

  const setActiveBranchId = (id: number) => setScope({ branchId: id });

  const branches      = STUB_BRANCHES.filter((b) => b.companyId === scope.companyId);
  const activeCompany = STUB_COMPANIES.find((c) => c.id === scope.companyId) ?? null;
  const activeBranch  = STUB_BRANCHES.find((b) => b.id === scope.branchId)  ?? null;

  return (
    <OrgContext.Provider
      value={{
        scope, setScope,
        companies: STUB_COMPANIES,
        branches,
        activeCompany,
        activeBranch,
        setActiveCompanyId,
        setActiveBranchId,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrgScope(): OrgContextValue {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrgScope must be used inside OrgProvider");
  return ctx;
}
