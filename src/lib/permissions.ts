import type { AdminRole } from '@/types/database';

/**
 * Route visibility per role.
 * admin sees everything; other roles see a subset.
 */
const ROUTE_ACCESS: Record<string, AdminRole[]> = {
  '/admin':              ['admin', 'compliance', 'finance', 'support'],
  '/admin/users':        ['admin', 'compliance', 'support'],
  '/admin/transactions': ['admin', 'compliance'],
  '/admin/kyc':          ['admin', 'compliance'],
  '/admin/settlement':   ['admin', 'finance'],
  '/admin/support':      ['admin', 'support'],
  '/admin/jobs':         ['admin'],
};

/**
 * Action permissions per role.
 * Used to gate UI buttons and Edge Function calls.
 */
const ACTION_PERMISSIONS: Record<string, AdminRole[]> = {
  'user.freeze':              ['admin', 'compliance'],
  'user.unfreeze':            ['admin', 'compliance'],
  'user.set_role':            ['admin'],
  'user.force_kyc_resubmit':  ['admin', 'compliance'],
  'merchant.approve':         ['admin', 'compliance'],
  'merchant.reject':          ['admin', 'compliance'],
  'merchant.suspend':         ['admin', 'compliance'],
  'merchant.set_payout':      ['admin', 'finance'],
  'kyc.approve':              ['admin', 'compliance'],
  'kyc.reject':               ['admin', 'compliance'],
  'kyc.request_resubmission': ['admin', 'compliance'],
  'settlement.generate':      ['admin', 'finance'],
  'settlement.mark_sent':     ['admin', 'finance'],
  'settlement.download':      ['admin', 'finance'],
  'recon.upload':             ['admin', 'finance'],
  'recon.resolve':            ['admin', 'finance'],
  'support.respond':          ['admin', 'support'],
  'support.close':            ['admin', 'support'],
  'support.reopen':           ['admin', 'support'],
  'danger.balance_adjust':    ['admin'],
  'danger.force_logout':      ['admin'],
  'danger.view_audit':        ['admin'],
  'jobs.enqueue':             ['admin'],
  'jobs.retry':               ['admin'],
};

export function canAccessRoute(pathname: string, roles: AdminRole[]): boolean {
  // Check exact match first, then check prefix for sub-routes like /admin/settlement/:id/reconcile
  const allowed = ROUTE_ACCESS[pathname];
  if (allowed) {
    return roles.some((r) => allowed.includes(r));
  }
  // For sub-routes, find the closest parent
  const segments = pathname.split('/');
  while (segments.length > 2) {
    segments.pop();
    const parent = segments.join('/');
    const parentAllowed = ROUTE_ACCESS[parent];
    if (parentAllowed) {
      return roles.some((r) => parentAllowed.includes(r));
    }
  }
  return false;
}

export function canPerformAction(action: string, roles: AdminRole[]): boolean {
  const allowed = ACTION_PERMISSIONS[action];
  if (!allowed) return false;
  return roles.some((r) => allowed.includes(r));
}

export function getVisibleNavItems(roles: AdminRole[]) {
  return Object.entries(ROUTE_ACCESS)
    .filter(([, allowed]) => roles.some((r) => allowed.includes(r)))
    .map(([path]) => path);
}

export { ROUTE_ACCESS, ACTION_PERMISSIONS };
