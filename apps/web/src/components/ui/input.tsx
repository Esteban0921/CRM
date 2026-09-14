import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { cx } from '@/lib/cx';

const fieldClass =
  'rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/80 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20';

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label: string };

export function Input({ label, id, className, ...props }: InputProps) {
  const inputId = id ?? props.name;
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <input id={inputId} className={cx(fieldClass, className)} {...props} />
    </label>
  );
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string };

export function Textarea({ label, id, className, ...props }: TextareaProps) {
  const inputId = id ?? props.name;
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <textarea id={inputId} className={cx(fieldClass, 'min-h-24', className)} {...props} />
    </label>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label?: string };

export function Select({ label, id, className, children, ...props }: SelectProps) {
  const select = (
    <select id={id ?? props.name} className={cx(fieldClass, 'pr-8', className)} {...props}>
      {children}
    </select>
  );
  if (!label) return select;
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-ink">{label}</span>
      {select}
    </label>
  );
}
