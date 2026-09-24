import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  ArrowLeftRight,
  Barcode,
  Bell,
  Boxes,
  ClipboardList,
  Cog,
  FileBarChart,
  Handshake,
  LayoutDashboard,
  MapPin,
  PackageCheck,
  PackagePlus,
  PlugZap,
  RadioTower,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  ShoppingCart,
  Tags,
  Truck,
  UserCog,
  Warehouse,
  PackageSearch,
} from 'lucide-react';

export type ModuleGroup =
  | 'Overview'
  | 'Inbound & Procurement'
  | 'Inventory Operations'
  | 'Outbound & Orders'
  | 'Catalog & Coding'
  | 'Network'
  | 'Platform & Governance';

export interface ModuleDefinition {
  /** Backend module key — matches `apps/<key>` and `/api/v1/<key>/`. */
  key: string;
  name: string;
  path: string;
  group: ModuleGroup;
  icon: LucideIcon;
  /** One-line summary shown on module landing pages. */
  summary: string;
  /** Capabilities planned for this module in later parts. */
  capabilities: string[];
}

export const MODULE_GROUPS: ModuleGroup[] = [
  'Overview',
  'Inbound & Procurement',
  'Inventory Operations',
  'Outbound & Orders',
  'Catalog & Coding',
  'Network',
  'Platform & Governance',
];

/**
 * Single source of truth for module navigation: it drives the sidebar and the
 * generated routes/landing pages. Adding a module here is the only frontend
 * change needed to surface a new backend module.
 */
export const MODULES: ModuleDefinition[] = [
  {
    key: 'organizations',
    name: 'Organizations',
    path: '/organizations',
    group: 'Network',
    icon: Handshake,
    summary: 'Tenants, legal entities and business units operating the supply network.',
    capabilities: [
      'Organization and legal-entity registry',
      'Multi-tenant scoping for every record',
      'Business-unit hierarchy and cost centers',
    ],
  },
  {
    key: 'warehouses',
    name: 'Warehouses',
    path: '/warehouses',
    group: 'Network',
    icon: Warehouse,
    summary: 'Warehouse and facility master data, operating calendars and capacity.',
    capabilities: [
      'Facility master data and operating hours',
      'Storage capacity and utilization targets',
      'Warehouse-level policies and defaults',
    ],
  },
  {
    key: 'locations',
    name: 'Locations',
    path: '/locations',
    group: 'Inventory Operations',
    icon: MapPin,
    summary: 'Zone → aisle → rack → bin hierarchy with mixed-SKU and capacity rules.',
    capabilities: [
      'Hierarchical location modelling',
      'Barcode labels per location',
      'Location constraints, pick paths and slotting',
    ],
  },
  {
    key: 'products',
    name: 'Products',
    path: '/products',
    group: 'Catalog & Coding',
    icon: Boxes,
    summary: 'Product master data, SKUs, variants, units of measure and attributes.',
    capabilities: [
      'Product / SKU catalogue with variants',
      'Units of measure and conversions',
      'Batch, serial and expiration tracking flags',
    ],
  },
  {
    key: 'pricing',
    name: 'Pricing',
    path: '/pricing',
    group: 'Catalog & Coding',
    icon: Tags,
    summary: 'Cost, list and contract pricing with effective-dated price rules.',
    capabilities: [
      'Price lists and effective-dated tiers',
      'Cost basis and margin visibility',
      'Customer/supplier-specific agreements',
    ],
  },
  {
    key: 'suppliers',
    name: 'Suppliers',
    path: '/suppliers',
    group: 'Inbound & Procurement',
    icon: Truck,
    summary: 'Vendor master data, performance scoring and lead-time history.',
    capabilities: [
      'Vendor profiles and contacts',
      'Lead times, MOQs and scorecards',
      'Supplier-item relationships',
    ],
  },
  {
    key: 'procurement',
    name: 'Procurement',
    path: '/procurement',
    group: 'Inbound & Procurement',
    icon: ShoppingCart,
    summary: 'Purchase requisitions and purchase orders with approval workflows.',
    capabilities: [
      'Requisition → purchase order lifecycle',
      'Approval thresholds and audit trail',
      'Partial receipts and backorders',
    ],
  },
  {
    key: 'receiving',
    name: 'Receiving',
    path: '/receiving',
    group: 'Inbound & Procurement',
    icon: PackagePlus,
    summary: 'Inbound shipments, appointment scheduling and ASN handling.',
    capabilities: [
      'Advanced shipping notices (ASN)',
      'Dock scheduling and gate check-in',
      'Discrepancy and damage capture',
    ],
  },
  {
    key: 'putaway',
    name: 'Putaway',
    path: '/putaway',
    group: 'Inbound & Procurement',
    icon: PackageCheck,
    summary: 'Directed putaway rules that place received goods in optimal locations.',
    capabilities: [
      'Rule-driven putaway strategies',
      'Capacity-aware location suggestion',
      'Mobile/scan confirmation',
    ],
  },
  {
    key: 'inventory',
    name: 'Inventory',
    path: '/inventory',
    group: 'Inventory Operations',
    icon: PackageSearch,
    summary: 'On-hand quantities by SKU, location, lot and serial with reservations.',
    capabilities: [
      'Real-time stock ledger per location',
      'Reservations, allocations and ATP',
      'Lot/serial/expiry traceability',
    ],
  },
  {
    key: 'transfers',
    name: 'Transfers',
    path: '/transfers',
    group: 'Inventory Operations',
    icon: ArrowLeftRight,
    summary: 'Warehouse-to-warehouse and intra-warehouse stock movement.',
    capabilities: [
      'Transfer orders with in-transit tracking',
      'Pick/pack/dispatch and receipt confirmation',
      'Inter-company movement support',
    ],
  },
  {
    key: 'orders',
    name: 'Orders',
    path: '/orders',
    group: 'Outbound & Orders',
    icon: ClipboardList,
    summary: 'Sales and outbound orders, allocation and priority handling.',
    capabilities: [
      'Order capture and validation',
      'Allocation and backorder management',
      'Priority rules and order waves',
    ],
  },
  {
    key: 'fulfillment',
    name: 'Fulfilment',
    path: '/fulfillment',
    group: 'Outbound & Orders',
    icon: Truck,
    summary: 'Pick, pack and ship execution with carrier integration.',
    capabilities: [
      'Wave/batch picking and packing',
      'Cartonization and shipping labels',
      'Carrier manifests and tracking',
    ],
  },
  {
    key: 'replenishment',
    name: 'Replenishment',
    path: '/replenishment',
    group: 'Inventory Operations',
    icon: RotateCcw,
    summary: 'Min/max, demand-based and forward-pick replenishment.',
    capabilities: [
      'Replenishment rules and triggers',
      'Forward-pick and dynamic slotting',
      'Suggested PO generation',
    ],
  },
  {
    key: 'stock_counts',
    name: 'Stock Counts',
    path: '/stock-counts',
    group: 'Inventory Operations',
    icon: ScanLine,
    summary: 'Cycle counts, full physical inventories and variance approval.',
    capabilities: [
      'Cycle count scheduling (ABC)',
      'Blind/recount workflows',
      'Variance investigation and adjustment posting',
    ],
  },
  {
    key: 'returns',
    name: 'Returns',
    path: '/returns',
    group: 'Outbound & Orders',
    icon: RotateCcw,
    summary: 'Customer returns, RMAs, inspection and disposition (restock/scrap).',
    capabilities: [
      'RMA issuance and receipt',
      'Inspection and disposition rules',
      'Restock, repair, scrap and credit notes',
    ],
  },
  {
    key: 'barcode',
    name: 'Barcode',
    path: '/barcode',
    group: 'Catalog & Coding',
    icon: Barcode,
    summary: 'Barcode symbologies, label templates and scan payload handling.',
    capabilities: [
      'GS1 / Code128 / QR generation',
      'Label templates per document type',
      'Scan parsing and validation rules',
    ],
  },
  {
    key: 'rfid',
    name: 'RFID',
    path: '/rfid',
    group: 'Catalog & Coding',
    icon: RadioTower,
    summary: 'EPC encoding, tag commissioning and reader integration.',
    capabilities: [
      'EPC generation and tag commissioning',
      'Reader/gateway event ingestion',
      'Cycle-count and dwell analytics',
    ],
  },
  {
    key: 'reports',
    name: 'Reports',
    path: '/reports',
    group: 'Platform & Governance',
    icon: FileBarChart,
    summary: 'Operational and analytical reporting with scheduled exports.',
    capabilities: [
      'Stock, movement and aging reports',
      'KPI dashboards per warehouse',
      'Scheduled CSV/XLSX exports',
    ],
  },
  {
    key: 'notifications',
    name: 'Notifications',
    path: '/notifications',
    group: 'Platform & Governance',
    icon: Bell,
    summary: 'Multi-channel alerts for threshold, SLA and workflow events.',
    capabilities: [
      'Email/in-app/webhook channels',
      'Subscriptions and digest rules',
      'Escalation policies',
    ],
  },
  {
    key: 'integrations',
    name: 'Integrations',
    path: '/integrations',
    group: 'Platform & Governance',
    icon: PlugZap,
    summary: 'ERP, WMS, carrier and marketplace connectors with retry semantics.',
    capabilities: [
      'Outbound webhooks with signing',
      'Inbound API keys and rate limits',
      'Sync logs and replay',
    ],
  },
  {
    key: 'audit',
    name: 'Audit',
    path: '/audit',
    group: 'Platform & Governance',
    icon: Activity,
    summary: 'Immutable audit trail of every material change and who made it.',
    capabilities: [
      'Field-level change history',
      'Actor, IP and device context',
      'Compliance exports',
    ],
  },
  {
    key: 'security',
    name: 'Security',
    path: '/security',
    group: 'Platform & Governance',
    icon: ShieldCheck,
    summary: 'Roles, permissions, API keys, sessions and security policy.',
    capabilities: [
      'Role-based access control',
      'API key and token lifecycle',
      'Session and lockout policy',
    ],
  },
  {
    key: 'configuration',
    name: 'Configuration',
    path: '/configuration',
    group: 'Platform & Governance',
    icon: Cog,
    summary: 'System settings, feature flags and reference/lookup data.',
    capabilities: [
      'Typed settings registry',
      'Feature flags and rollout control',
      'Reference data maintenance',
    ],
  },
  {
    key: 'identity',
    name: 'Identity',
    path: '/identity',
    group: 'Platform & Governance',
    icon: UserCog,
    summary: 'Users, authentication, SSO and profile management.',
    capabilities: [
      'User and profile administration',
      'SSO / OIDC and MFA enrolment',
      'Password policy and invitations',
    ],
  },
];

export const MODULES_BY_KEY: Record<string, ModuleDefinition> = Object.fromEntries(
  MODULES.map((module) => [module.key, module]),
);

export function modulesInGroup(group: ModuleGroup): ModuleDefinition[] {
  return MODULES.filter((module) => module.group === group);
}

export const dashboardNavItem = {
  key: 'dashboard',
  name: 'Dashboard',
  path: '/',
  icon: LayoutDashboard,
} as const;
