import { AnalyticsLedger } from '@mv/shared';

/** 紀錄 — the viewer's read-only recognition ledger. */
export function Analytics() {
  return <AnalyticsLedger variant="viewer" />;
}
