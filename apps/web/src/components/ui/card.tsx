import type { ReactNode } from 'react';
import { Surface } from '@/components/ui/surface';

/**
 * `Card` se conserva como envoltorio de `Surface` nivel 1 para no tocar las
 * once pantallas que ya la usan (TASK-0144). Lo nuevo se escribe con
 * `<Surface level>` directamente, que es donde vive la escala de elevacion.
 */
export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <Surface level={1} className={className}>
      {children}
    </Surface>
  );
}
