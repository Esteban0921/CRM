'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cx } from '@/lib/cx';
import type { Family } from '@/lib/api';

/**
 * Un unico selector de familia para todo el tablero (TASK-0126).
 *
 * Antes cada tarjeta renderizaba su propio `<select>` con TODAS las familias:
 * coste O(tarjetas x familias). Con 2.068 facturas medidas por la auditoria
 * eran 167.801 nodos del DOM, de los cuales **134.420 eran `<option>`**, y 13,6
 * segundos hasta ver la primera tarjeta. Con 200 facturas y 100 familias ya
 * son 20.000 `<option>`.
 *
 * Ademas un `<select>` plano no se puede buscar: con 65 familias en la base de
 * datos habia que recorrerlo a ciegas, y los nombres largos salian cortados
 * («Familia Garcia Perc»), que es justo el peor sitio para equivocarse.
 */
export function FamilyPickerDialog({
  open,
  families,
  currentFamilyId,
  invoiceLabel,
  onPick,
  onClose,
}: {
  open: boolean;
  families: Family[];
  currentFamilyId: string | null;
  invoiceLabel: string;
  onPick: (familyId: string | null) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
    }
  }, [open]);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return families;
    return families.filter((family) => family.name.toLowerCase().includes(needle));
  }, [families, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, matches.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const family = matches[activeIndex];
      if (family) onPick(family.id);
    }
  }

  return (
    <Dialog open={open} title={`Asignar familia · ${invoiceLabel}`} onClose={onClose} size="md">
      <div className="flex flex-col gap-3" onKeyDown={handleKeyDown}>
        <Input
          label="Buscar familia"
          autoFocus
          placeholder="Escribe parte del nombre"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <ul ref={listRef} className="flex max-h-72 flex-col gap-1 overflow-y-auto">
          <li>
            <button
              type="button"
              onClick={() => onPick(null)}
              className={cx(
                'w-full rounded-lg px-3 py-2 text-left text-sm transition-colors',
                currentFamilyId === null
                  ? 'bg-brand-soft text-ink'
                  : 'text-muted hover:bg-brand-tint hover:text-ink',
              )}
            >
              Sin asignar
            </button>
          </li>
          {matches.map((family, index) => (
            <li key={family.id}>
              <button
                type="button"
                onClick={() => onPick(family.id)}
                className={cx(
                  'w-full rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  index === activeIndex ? 'bg-brand-tint' : '',
                  family.id === currentFamilyId
                    ? 'bg-brand-soft font-medium text-ink'
                    : 'text-ink-2 hover:bg-brand-tint hover:text-ink',
                )}
              >
                {family.name}
              </button>
            </li>
          ))}
          {matches.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted">Ninguna familia coincide.</li>
          )}
        </ul>
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cerrar sin asignar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
