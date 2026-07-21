'use client';

/**
 * SenderVerificationCard (C5)
 *
 * Displays sender verification results in plain language.
 * Normal users see a status badge + 1–4 plain-English signals.
 * Technical header details (SPF/DKIM/DMARC/domains) are hidden inside a
 * collapsed <details> section that is closed by default.
 *
 * The component is deliberately compact so it doesn't dominate the results page.
 * Renders nothing if `verification` is null/undefined.
 */

import type { SenderVerification } from '@/lib/api';

interface Props {
  verification: SenderVerification | null | undefined;
}

const STATUS_CONFIG = {
  verified: {
    label: 'Verified',
    badgeClass: 'bg-green-500/15 text-green-600 border border-green-500/30',
    iconClass: 'text-green-500',
    icon: '✓',
  },
  warning: {
    label: 'Warning',
    badgeClass: 'bg-yellow-500/15 text-yellow-600 border border-yellow-500/30',
    iconClass: 'text-yellow-500',
    icon: '⚠',
  },
  suspicious: {
    label: 'Suspicious',
    badgeClass: 'bg-red-500/15 text-red-600 border border-red-500/30',
    iconClass: 'text-red-500',
    icon: '✕',
  },
  unavailable: {
    label: 'Unavailable',
    badgeClass: 'bg-muted text-muted-foreground border border-muted',
    iconClass: 'text-muted-foreground',
    icon: '—',
  },
} as const;

export function SenderVerificationCard({ verification }: Props) {
  if (!verification) return null;

  const status = verification.status in STATUS_CONFIG
    ? verification.status
    : 'unavailable';
  const cfg = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG];

  const hasTechnicalDetails =
    verification.technical_details &&
    Object.values(verification.technical_details).some((v) =>
      v !== null && v !== undefined && (Array.isArray(v) ? v.length > 0 : true)
    );

  const td = verification.technical_details;

  return (
    <div
      className="rounded-lg border bg-card p-4 space-y-3"
      aria-label="Sender verification result"
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-foreground">
          Sender Verification
        </span>
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.badgeClass}`}
        >
          <span className={cfg.iconClass} aria-hidden="true">
            {cfg.icon}
          </span>
          {cfg.label}
        </span>
      </div>

      {/* Plain-language summary */}
      <p className="text-sm text-muted-foreground leading-snug">
        {verification.summary}
      </p>

      {/* Signals (plain language, ≤4) */}
      {verification.signals && verification.signals.length > 0 && (
        <ul className="space-y-1.5">
          {verification.signals.map((signal, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span
                className="mt-0.5 shrink-0 text-yellow-500"
                aria-hidden="true"
              >
                •
              </span>
              <span className="text-foreground/80">{signal}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Collapsed technical details section */}
      {hasTechnicalDetails && td && (
        <details className="group">
          <summary
            className="cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors select-none list-none flex items-center gap-1"
            aria-label="Toggle technical details"
          >
            <span className="group-open:hidden">▶</span>
            <span className="hidden group-open:inline">▼</span>
            Show technical details
          </summary>

          <div className="mt-3 rounded-md bg-muted/50 p-3 space-y-2 text-xs font-mono">
            {td.from_domain && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">From domain</span>
                <span className="text-foreground break-all">{td.from_domain}</span>
              </div>
            )}
            {td.reply_to_domain && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Reply-To</span>
                <span className="text-foreground break-all">{td.reply_to_domain}</span>
              </div>
            )}
            {td.return_path_domain && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Return-Path</span>
                <span className="text-foreground break-all">{td.return_path_domain}</span>
              </div>
            )}
            {td.spf && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">SPF</span>
                <span
                  className={
                    td.spf === 'pass'
                      ? 'text-green-500'
                      : td.spf === 'fail'
                      ? 'text-red-500'
                      : 'text-yellow-500'
                  }
                >
                  {td.spf}
                </span>
              </div>
            )}
            {td.dkim && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">DKIM</span>
                <span
                  className={
                    td.dkim === 'pass'
                      ? 'text-green-500'
                      : td.dkim === 'fail' || td.dkim === 'none'
                      ? 'text-red-500'
                      : 'text-yellow-500'
                  }
                >
                  {td.dkim}
                </span>
              </div>
            )}
            {td.dmarc && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">DMARC</span>
                <span
                  className={
                    td.dmarc === 'pass'
                      ? 'text-green-500'
                      : td.dmarc === 'fail'
                      ? 'text-red-500'
                      : 'text-yellow-500'
                  }
                >
                  {td.dmarc}
                </span>
              </div>
            )}
            {td.link_domains && td.link_domains.length > 0 && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Link domains</span>
                <span className="text-foreground break-all">
                  {td.link_domains.slice(0, 5).join(', ')}
                  {td.link_domains.length > 5 && ` +${td.link_domains.length - 5} more`}
                </span>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
