import type { ComponentType } from "react";
import type { SvgIconProps } from "@mui/material/SvgIcon";
import DashboardOutlinedIcon       from "@mui/icons-material/DashboardOutlined";
import ReceiptLongOutlinedIcon     from "@mui/icons-material/ReceiptLongOutlined";
import AccountBalanceWalletOutlinedIcon from "@mui/icons-material/AccountBalanceWalletOutlined";
import DescriptionOutlinedIcon     from "@mui/icons-material/DescriptionOutlined";
import PeopleOutlinedIcon          from "@mui/icons-material/PeopleOutlined";
import LocalOfferOutlinedIcon      from "@mui/icons-material/LocalOfferOutlined";
import AssignmentOutlinedIcon      from "@mui/icons-material/AssignmentOutlined";
import LocalShippingOutlinedIcon   from "@mui/icons-material/LocalShippingOutlined";
import ReceiptOutlinedIcon         from "@mui/icons-material/ReceiptOutlined";
import PaymentOutlinedIcon         from "@mui/icons-material/PaymentOutlined";
import StoreOutlinedIcon           from "@mui/icons-material/StoreOutlined";
import Inventory2OutlinedIcon      from "@mui/icons-material/Inventory2Outlined";
import WarehouseOutlinedIcon       from "@mui/icons-material/WarehouseOutlined";
import SyncAltOutlinedIcon         from "@mui/icons-material/SyncAltOutlined";
import SwapHorizOutlinedIcon       from "@mui/icons-material/SwapHorizOutlined";
import LayersOutlinedIcon          from "@mui/icons-material/LayersOutlined";
import AccountTreeOutlinedIcon     from "@mui/icons-material/AccountTreeOutlined";
import MenuBookOutlinedIcon        from "@mui/icons-material/MenuBookOutlined";
import AccountBalanceOutlinedIcon  from "@mui/icons-material/AccountBalanceOutlined";
import ShowChartOutlinedIcon       from "@mui/icons-material/ShowChartOutlined";
import SummarizeOutlinedIcon       from "@mui/icons-material/SummarizeOutlined";
import ManageAccountsOutlinedIcon  from "@mui/icons-material/ManageAccountsOutlined";
import CorporateFareOutlinedIcon   from "@mui/icons-material/CorporateFareOutlined";
import TaskOutlinedIcon            from "@mui/icons-material/TaskOutlined";
import SettingsOutlinedIcon        from "@mui/icons-material/SettingsOutlined";
import ScienceOutlinedIcon         from "@mui/icons-material/ScienceOutlined";

export type IconComponent = ComponentType<SvgIconProps>;

export interface NavItem {
  labelKey: string;
  Icon: IconComponent;
  path: string;
  permission?: string;
}

export interface NavSection {
  labelKey: string;
  items: NavItem[];
}

export const NAV_CONFIG: NavSection[] = [
  {
    labelKey: "nav.section.main",
    items: [
      { labelKey: "nav.dashboard", Icon: DashboardOutlinedIcon, path: "/app/dashboard" },
    ],
  },
  {
    labelKey: "nav.section.sales",
    items: [
      { labelKey: "nav.sales.invoices",    Icon: ReceiptLongOutlinedIcon,         path: "/app/sales/invoices",       permission: "sales.invoice.read" },
      { labelKey: "nav.sales.collections", Icon: AccountBalanceWalletOutlinedIcon, path: "/app/sales/collections",    permission: "sales.collection.read" },
      { labelKey: "nav.sales.creditNotes", Icon: DescriptionOutlinedIcon,          path: "/app/sales/credit-notes",   permission: "sales.credit_note.read" },
      { labelKey: "nav.sales.customers",   Icon: PeopleOutlinedIcon,               path: "/app/sales/customers",      permission: "master_data.customer.read" },
      { labelKey: "nav.sales.priceLists",  Icon: LocalOfferOutlinedIcon,           path: "/app/sales/price-lists",    permission: "sales.price_list.read" },
    ],
  },
  {
    labelKey: "nav.section.purchasing",
    items: [
      { labelKey: "nav.purchasing.orders",    Icon: AssignmentOutlinedIcon,    path: "/app/purchasing/orders" },
      { labelKey: "nav.purchasing.receipts",  Icon: LocalShippingOutlinedIcon, path: "/app/purchasing/receipts" },
      { labelKey: "nav.purchasing.invoices",  Icon: ReceiptOutlinedIcon,       path: "/app/purchasing/invoices" },
      { labelKey: "nav.purchasing.payments",  Icon: PaymentOutlinedIcon,       path: "/app/purchasing/payments" },
      { labelKey: "nav.purchasing.suppliers", Icon: StoreOutlinedIcon,         path: "/app/purchasing/suppliers", permission: "master_data.supplier.read" },
    ],
  },
  {
    labelKey: "nav.section.inventory",
    items: [
      { labelKey: "nav.inventory.products",  Icon: Inventory2OutlinedIcon, path: "/app/inventory/products",  permission: "master_data.product.read" },
      { labelKey: "nav.inventory.balances",  Icon: WarehouseOutlinedIcon,  path: "/app/inventory/balances",  permission: "inventory.balance.read" },
      { labelKey: "nav.inventory.movements", Icon: SyncAltOutlinedIcon,    path: "/app/inventory/movements", permission: "inventory.movement.read" },
      { labelKey: "nav.inventory.transfers", Icon: SwapHorizOutlinedIcon,  path: "/app/inventory/transfers", permission: "inventory.movement.read" },
      { labelKey: "nav.inventory.batches",   Icon: LayersOutlinedIcon,     path: "/app/inventory/batches",   permission: "inventory.batch.read" },
    ],
  },
  {
    labelKey: "nav.section.accounting",
    items: [
      { labelKey: "nav.accounting.accounts",     Icon: AccountTreeOutlinedIcon,    path: "/app/accounting/accounts",      permission: "accounting.accounts.view" },
      { labelKey: "nav.accounting.journal",      Icon: MenuBookOutlinedIcon,        path: "/app/accounting/journal",       permission: "accounting.journal_entries.view" },
      { labelKey: "nav.accounting.trialBalance", Icon: AccountBalanceOutlinedIcon,  path: "/app/accounting/trial-balance", permission: "accounting.reports.view" },
      { labelKey: "nav.accounting.pnl",          Icon: ShowChartOutlinedIcon,       path: "/app/accounting/pnl",           permission: "accounting.reports.view" },
      { labelKey: "nav.accounting.balanceSheet", Icon: SummarizeOutlinedIcon,       path: "/app/accounting/balance-sheet", permission: "accounting.reports.view" },
    ],
  },
  {
    labelKey: "nav.section.system",
    items: [
      { labelKey: "nav.system.users",        Icon: ManageAccountsOutlinedIcon, path: "/app/system/users" },
      { labelKey: "nav.system.organization", Icon: CorporateFareOutlinedIcon,  path: "/app/system/organization", permission: "organization.company.read" },
      { labelKey: "nav.system.approvals",    Icon: TaskOutlinedIcon,           path: "/app/system/approvals",    permission: "sales.approval.read" },
      { labelKey: "nav.system.settings",     Icon: SettingsOutlinedIcon,       path: "/app/system/settings" },
      { labelKey: "nav.demo",                Icon: ScienceOutlinedIcon,        path: "/app/demo" },
    ],
  },
];

export const ROUTE_LABEL_MAP: Record<string, string> = {
  "/app/dashboard": "nav.dashboard",
  "/app/demo": "nav.demo",
  // Sales
  "/app/sales/invoices":     "nav.sales.invoices",
  "/app/sales/collections":  "nav.sales.collections",
  "/app/sales/credit-notes": "nav.sales.creditNotes",
  "/app/sales/customers":    "nav.sales.customers",
  "/app/sales/price-lists":  "nav.sales.priceLists",
  // Purchasing
  "/app/purchasing/orders":    "nav.purchasing.orders",
  "/app/purchasing/receipts":  "nav.purchasing.receipts",
  "/app/purchasing/invoices":  "nav.purchasing.invoices",
  "/app/purchasing/payments":  "nav.purchasing.payments",
  "/app/purchasing/suppliers": "nav.purchasing.suppliers",
  // Inventory
  "/app/inventory/products":  "nav.inventory.products",
  "/app/inventory/balances":  "nav.inventory.balances",
  "/app/inventory/movements": "nav.inventory.movements",
  "/app/inventory/transfers": "nav.inventory.transfers",
  "/app/inventory/batches":   "nav.inventory.batches",
  // Accounting
  "/app/accounting/accounts":       "nav.accounting.accounts",
  "/app/accounting/journal":        "nav.accounting.journal",
  "/app/accounting/trial-balance":  "nav.accounting.trialBalance",
  "/app/accounting/pnl":            "nav.accounting.pnl",
  "/app/accounting/balance-sheet":  "nav.accounting.balanceSheet",
  // System
  "/app/system/users":        "nav.system.users",
  "/app/system/organization": "nav.system.organization",
  "/app/system/approvals":    "nav.system.approvals",
  "/app/system/settings":     "nav.system.settings",
};

export const HEADER_HEIGHT  = 56;
export const SIDEBAR_WIDTH  = 220;
export const RAIL_WIDTH     = 64;
