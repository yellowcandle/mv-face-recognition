import type { PropsWithChildren, HTMLAttributes } from 'react';

interface CardProps extends PropsWithChildren<HTMLAttributes<HTMLDivElement>> {
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingStyles: Record<string, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};

/** A hairline panel on the page ground. No fill, no shadow: prefer plain rules where they work. */
export function Card({ padding = 'md', className = '', children, ...props }: CardProps) {
  return (
    <div
      className={`rounded-md border border-carbon-deep/13 ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
