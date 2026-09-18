import type { ButtonHTMLAttributes } from 'react';
import { cx } from '@/lib/cx';

/**
 * Feedback al pulsar (TASK-0152).
 *
 * La medicion de la auditoria: ningun boton, tarjeta o enlace cambiaba en
 * `:active`. Un producto sin respuesta al clic se lee como «basico» aunque
 * todo lo demas este bien.
 *
 * `danger` baja de rojo solido a contorno: era el unico boton saturado de la
 * aplicacion y estaba puesto como tercera accion primaria de cada ficha
 * («Anonimizar (RGPD)»). El nombre accesible no cambia, que hay e2e que lo
 * buscan (TASK-0153).
 */
const variants = {
  primary:
    'bg-brand text-brand-fg hover:bg-brand-hover active:bg-brand-strong shadow-[var(--shadow-1)]',
  secondary:
    'bg-surface text-ink border border-line hover:border-line-strong hover:bg-raised active:bg-canvas',
  ghost: 'text-muted hover:text-ink hover:bg-brand-tint active:bg-brand-soft',
  danger:
    'border border-danger-line bg-danger-bg text-danger-fg hover:bg-danger-line/30 active:bg-danger-line/50',
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
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium',
        'transition duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
        // El anillo de foco estaba bien medido y es accesible: se conserva tal cual.
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
