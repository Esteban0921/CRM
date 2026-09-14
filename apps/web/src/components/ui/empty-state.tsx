import type { ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-line bg-paper/60 px-5 py-8">
      <p className="font-medium text-ink">{title}</p>
      <p className="max-w-md text-sm text-muted">{description}</p>
      {action}
    </div>
  );
}
