import type { ReactNode } from 'react';

interface MastheadProps {
  /** Small tracked line above the title, e.g. "MV FACE RECOGNITION · 全民造星 IV". */
  eyebrow: string;
  /** The folio's name, set in the printed serif. */
  title: string;
  /** The tracked English line beside the title. */
  latin: string;
  /** Viewer headings are 46px, admin headings 44px. */
  size?: 'lg' | 'md';
  /** The right-hand slot: counters, a select, a stamp. Varies per page. */
  children?: ReactNode;
}

/**
 * The masthead every page shares: eyebrow, title + latin, and a right-hand slot.
 *
 * Before this, seven pages carried their own copy — 176 lines that differed only in
 * the right slot (and a 2px title size). Keeping the structure here means a change to
 * the masthead is one edit, and the folio identity cannot drift between pages.
 */
export function Masthead({ eyebrow, title, latin, size = 'lg', children }: MastheadProps) {
  return (
    <div className="flex flex-row items-end justify-between gap-6">
      <div className="flex flex-col gap-1.5">
        <div className="font-mono text-[10px] tracking-[0.28em] text-carbon-soft">{eyebrow}</div>
        <div className="flex flex-row items-baseline gap-3.5">
          <h1
            className={`font-serif ${
              size === 'lg' ? 'text-[46px]' : 'text-[44px]'
            } font-black leading-none tracking-[0.06em] text-carbon`}
          >
            {title}
          </h1>
          <span className="font-mono text-[11px] tracking-[0.26em] text-ledger">{latin}</span>
        </div>
      </div>
      {children ? (
        <div className="flex flex-row items-center gap-4 pb-1">{children}</div>
      ) : null}
    </div>
  );
}
