import type { PropsWithChildren, HTMLAttributes } from 'react';

interface BadgeProps extends PropsWithChildren<HTMLAttributes<HTMLSpanElement>> {
  variant?: 'success' | 'warning' | 'error' | 'neutral';
  size?: 'sm' | 'md';
}

/** A hairline mark for plain status. For bands and human decisions, use `Stamp`. */
const variantStyles: Record<string, string> = {
  success: 'text-carbon border-carbon',
  warning: 'text-stamp border-stamp',
  error: 'text-ink-muted border-ink-muted',
  neutral: 'text-carbon-soft border-carbon-deep/33',
};

const sizeStyles: Record<string, string> = {
  sm: 'px-1.5 py-0.5',
  md: 'px-2 py-0.5',
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
      className={`inline-block rounded-xs border font-kai text-[12px] leading-tight ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
