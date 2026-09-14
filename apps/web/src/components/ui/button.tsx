import type { ButtonHTMLAttributes } from 'react';
import { cx } from '@/lib/cx';

const variants = {
  primary: 'bg-brand text-white hover:bg-brand-hover',
  secondary: 'bg-paper text-ink border border-line hover:bg-canvas',
  ghost: 'text-muted hover:text-ink hover:bg-paper/80',
  danger: 'bg-rose-600 text-white hover:bg-rose-700',
} as const;

const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
} as const;

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
};

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: Props) {
  return (
    <button
      type={type}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
