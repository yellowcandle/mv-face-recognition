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

/** A card is a slip of the same paper: a ruled edge, no shadow, no rounding. */
export function Card({
  padding = 'md',
  className = '',
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={`rounded-none border border-carbon/35 bg-paper-light ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
