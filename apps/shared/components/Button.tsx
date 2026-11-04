import type { PropsWithChildren, ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  /** The keyboard shortcut shown after the label, e.g. `1` or `↓`. Display only: bind it yourself. */
  keycap?: ReactNode;
}

const variantStyles: Record<string, string> = {
  primary: 'border border-stamp bg-stamp font-bold text-paper-light hover:bg-stamp/90',
  secondary: 'border border-carbon-deep/33 text-carbon hover:bg-tint',
  ghost: 'border border-transparent text-carbon hover:bg-tint',
  destructive: 'border border-stamp text-stamp hover:bg-stamp hover:text-paper-light',
};

const sizeStyles: Record<string, string> = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-10 px-4 text-[15px]',
  lg: 'h-11 px-5 text-[15px]',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  keycap,
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-kai transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
      {keycap != null ? (
        <kbd
          className={`font-mono text-[12px] font-normal ${
            variant === 'primary' ? 'text-paper-light/80' : 'text-ink-muted'
          }`}
        >
          {keycap}
        </kbd>
      ) : null}
    </button>
  );
}
