import type { PropsWithChildren, HTMLAttributes } from 'react';

interface CardProps extends PropsWithChildren<HTMLAttributes<HTMLDivElement>> {
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingStyles: Record<string, string> = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

export function Card({
  padding = 'md',
  className = '',
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-none ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
