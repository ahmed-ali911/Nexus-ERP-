import type { ComponentType } from "react";
import type { SvgIconProps } from "@mui/material/SvgIcon";
import DashboardOutlinedIcon   from "@mui/icons-material/DashboardOutlined";
import Inventory2OutlinedIcon  from "@mui/icons-material/Inventory2Outlined";
import WarehouseOutlinedIcon   from "@mui/icons-material/WarehouseOutlined";
import ReceiptOutlinedIcon      from "@mui/icons-material/ReceiptOutlined";
import AccountBalanceOutlinedIcon from "@mui/icons-material/AccountBalanceOutlined";
import ShoppingCartOutlinedIcon from "@mui/icons-material/ShoppingCartOutlined";
import SettingsOutlinedIcon     from "@mui/icons-material/SettingsOutlined";
import ScienceOutlinedIcon      from "@mui/icons-material/ScienceOutlined";

export type IconComponent = ComponentType<SvgIconProps>;

export interface NavItem {
  /** i18n key */
  labelKey: string;
  Icon: IconComponent;
  /** Absolute app path */
  path: string;
  /** If set, user must have this permission string (or "*") to see the item */
  permission?: string;
}

export interface NavSection {
  /** i18n key for the section heading */
  labelKey: string;
  items: NavItem[];
}

export const NAV_CONFIG: NavSection[] = [
  {
    labelKey: "nav.section.main",
    items: [
      { labelKey: "nav.dashboard", Icon: DashboardOutlinedIcon,       path: "/app/dashboard" },
      { labelKey: "nav.products",  Icon: Inventory2OutlinedIcon,       path: "/app/products",   permission: "products.view" },
      { labelKey: "nav.inventory", Icon: WarehouseOutlinedIcon,        path: "/app/inventory",  permission: "inventory.view" },
    ],
  },
  {
    labelKey: "nav.section.finance",
    items: [
      { labelKey: "nav.invoices",   Icon: ReceiptOutlinedIcon,           path: "/app/invoices",   permission: "sales.invoice.view" },
      { labelKey: "nav.accounting", Icon: AccountBalanceOutlinedIcon,    path: "/app/accounting", permission: "accounting.view" },
      { labelKey: "nav.purchasing", Icon: ShoppingCartOutlinedIcon,      path: "/app/purchasing", permission: "purchasing.view" },
    ],
  },
  {
    labelKey: "nav.section.system",
    items: [
      { labelKey: "nav.settings", Icon: SettingsOutlinedIcon, path: "/app/settings" },
      { labelKey: "nav.demo",     Icon: ScienceOutlinedIcon,  path: "/app/demo" },
    ],
  },
];

/** Flat map: route prefix → i18n breadcrumb key */
export const ROUTE_LABEL_MAP: Record<string, string> = {
  "/app/dashboard":  "nav.dashboard",
  "/app/products":   "nav.products",
  "/app/inventory":  "nav.inventory",
  "/app/invoices":   "nav.invoices",
  "/app/accounting": "nav.accounting",
  "/app/purchasing": "nav.purchasing",
  "/app/settings":   "nav.settings",
  "/app/demo":       "nav.demo",
};

export const HEADER_HEIGHT  = 56;   // px
export const SIDEBAR_WIDTH  = 220;  // px — expanded
export const RAIL_WIDTH     = 64;   // px — collapsed icon-rail
