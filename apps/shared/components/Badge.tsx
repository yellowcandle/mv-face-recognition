import type { PropsWithChildren, HTMLAttributes } from 'react';

interface BadgeProps extends PropsWithChildren<HTMLAttributes<HTMLSpanElement>> {
  variant?: 'success' | 'warning' | 'error' | 'neutral';
  size?: 'sm' | 'md';
}

const variantStyles: Record<string, string> = {
  success: 'bg-green-900/40 text-green-400 border-green-800',
  warning: 'bg-amber-900/40 text-amber-400 border-amber-800',
  error: 'bg-red-900/40 text-red-400 border-red-800',
  neutral: 'bg-slate-800 text-slate-400 border-slate-700',
};

const sizeStyles: Record<string, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
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
      className={`inline-flex items-center rounded-full border font-medium ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
