import type { PropsWithChildren, HTMLAttributes } from 'react';

interface BadgeProps extends PropsWithChildren<HTMLAttributes<HTMLSpanElement>> {
  variant?: 'success' | 'warning' | 'error' | 'neutral';
  size?: 'sm' | 'md';
}

/** A badge is a hand stamp: a bordered mark, never a coloured pill. */
const variantStyles: Record<string, string> = {
  success: 'text-carbon border-carbon',
  warning: 'text-stamp border-stamp',
  error: 'text-ledger border-ledger',
  neutral: 'text-carbon-soft border-carbon/40',
};

const sizeStyles: Record<string, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-[11px]',
};

export function Badge({
  variant = 'neutral',
  size = 'sm',
  className = '',
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={`inline-block -rotate-2 rounded-none border bg-transparent font-kai tracking-[0.1em] ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
