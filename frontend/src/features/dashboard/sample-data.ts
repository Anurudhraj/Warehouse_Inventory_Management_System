/**
 * Placeholder figures for the Part 1 dashboard.
 *
 * These values exist purely to exercise the design system; they are replaced
 * by live API data as each business module is implemented (Parts 2+).
 */
export interface WarehouseUtilization {
  code: string;
  name: string;
  utilization: number;
  bins: number;
  skus: number;
}

export interface ActivityEntry {
  id: string;
  actor: string;
  action: string;
  subject: string;
  timestamp: string;
  module: string;
}

export const warehouseUtilization: WarehouseUtilization[] = [
  { code: 'WH-01', name: 'Central DC — Chicago', utilization: 82, bins: 12_480, skus: 3_142 },
  { code: 'WH-02', name: 'West Hub — Reno', utilization: 64, bins: 8_220, skus: 2_058 },
  { code: 'WH-03', name: 'East Cross-dock — Newark', utilization: 47, bins: 3_960, skus: 894 },
  { code: 'WH-04', name: 'Cold Storage — Dallas', utilization: 91, bins: 1_840, skus: 412 },
];

export const recentActivity: ActivityEntry[] = [
  {
    id: 'a1',
    actor: 'M. Alvarez',
    action: 'received PO',
    subject: 'PO-2026-004182 · 42 lines',
    timestamp: new Date(Date.now() - 6 * 60 * 1000).toISOString(),
    module: 'receiving',
  },
  {
    id: 'a2',
    actor: 'System',
    action: 'posted adjustment',
    subject: 'Cycle count CC-1092 · bin A-14-03',
    timestamp: new Date(Date.now() - 34 * 60 * 1000).toISOString(),
    module: 'stock_counts',
  },
  {
    id: 'a3',
    actor: 'J. Whitfield',
    action: 'dispatched transfer',
    subject: 'TR-8841 · WH-01 → WH-02',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    module: 'transfers',
  },
  {
    id: 'a4',
    actor: 'P. Osei',
    action: 'approved replenishment',
    subject: 'RP-3320 · forward-pick zone',
    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    module: 'replenishment',
  },
  {
    id: 'a5',
    actor: 'S. Nakamura',
    action: 'created wave',
    subject: 'WAVE-2210 · 138 orders',
    timestamp: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(),
    module: 'fulfillment',
  },
];

/** Daily order lines processed, last 12 hours (sample throughput). */
export const throughputSeries = [
  { label: '00', value: 320 },
  { label: '02', value: 210 },
  { label: '04', value: 184 },
  { label: '06', value: 402 },
  { label: '08', value: 812 },
  { label: '10', value: 1_240 },
  { label: '12', value: 1_080 },
  { label: '14', value: 1_360 },
  { label: '16', value: 1_190 },
  { label: '18', value: 940 },
  { label: '20', value: 620 },
  { label: '22', value: 410 },
];
