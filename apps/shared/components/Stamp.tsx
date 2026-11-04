import type { HTMLAttributes } from 'react';
import { BAND_STAMP } from '../lib/bands';
import type { Band } from '../lib/bands';

type Tone = 'stamp' | 'carbon' | 'muted';

interface StampProps extends HTMLAttributes<HTMLSpanElement> {
  /** A match-score band: supplies the word and the tone. */
  band?: Band;
  tone?: Tone;
  /** A human decision (已核對, 作廢): tilted, bold, on a ground fill so it reads over a photo. */
  tilt?: boolean;
}

const TONE_INK: Record<Tone, string> = {
  stamp: 'text-stamp border-stamp',
  carbon: 'text-carbon border-carbon',
  muted: 'text-ink-muted border-ink-muted',
};

/** The stamp mark. Upright for bands and quality; `tilt` only where a human decided. */
export function Stamp({
  band,
  tone,
  tilt = false,
  className = '',
  children,
  ...props
}: StampProps) {
  const ink = TONE_INK[tone ?? (band ? BAND_STAMP[band].tone : 'stamp')];
  return (
    <span
      className={`inline-block shrink-0 whitespace-nowrap rounded-xs border px-1.5 py-0.5 font-kai text-[12px] leading-tight ${ink} ${
        tilt ? '-rotate-[4deg] bg-ground/93 font-bold' : ''
      } ${className}`}
      {...props}
    >
      {children ?? (band ? BAND_STAMP[band].word : null)}
    </span>
  );
}
