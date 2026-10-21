import type { PropsWithChildren, ButtonHTMLAttributes } from 'react';

interface ButtonProps extends PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
}

/** A button is a rubber stamp: square, inked, and it leaves a mark. */
const variantStyles: Record<string, string> = {
  primary: 'bg-stamp text-paper-light border border-stamp hover:bg-stamp/90 font-bold',
  secondary:
    'bg-transparent text-carbon border border-carbon/60 hover:bg-carbon hover:text-paper-light',
  ghost:
    'bg-transparent text-carbon-soft border border-transparent hover:text-carbon hover:border-carbon/30',
  destructive:
    'bg-transparent text-stamp border border-stamp/70 hover:bg-stamp hover:text-paper-light',
};

const sizeStyles: Record<string, string> = {
  sm: 'px-2.5 py-1 text-[11px]',
  md: 'px-3.5 py-1.5 text-[13px]',
  lg: 'px-4 py-2.5 text-[15px]',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-none font-kai tracking-[0.08em] transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
