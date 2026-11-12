import type { ReactNode } from 'react';

interface MastheadProps {
  title: string;
  /** The one line under the title saying what this page is for. */
  hint?: string;
  /** Right slot alignment. Text sits on the baseline (`end`); a lone button centres. */
  align?: 'end' | 'center';
  /** The right-hand slot: a note, a select, a button. Varies per page. */
  children?: ReactNode;
  /** On phones, give the right slot its own full-width line (for selects and button rows). */
  fill?: boolean;
}

/** The page head every page shares: 32px title, a hint under it, and a right-hand slot. */
export function Masthead({ title, hint, align = 'end', children, fill = false }: MastheadProps) {
  return (
    <div
      className={`flex flex-row flex-wrap justify-between gap-x-6 gap-y-3 ${
        align === 'center' ? 'items-center' : 'items-end'
      }`}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="font-kai text-[32px] font-normal leading-tight text-carbon-deep">{title}</h1>
        {hint ? <p className="font-kai text-[14px] text-carbon-soft">{hint}</p> : null}
      </div>
      {children ? (
        <div
          className={`flex shrink-0 flex-row items-center gap-4 font-kai text-[13px] text-ink-muted ${
            fill ? 'max-sm:w-full' : ''
          }`}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
