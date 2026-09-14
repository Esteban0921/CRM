import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-canvas">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <p className="text-sm font-semibold tracking-tight text-brand">CRM Transporte</p>
        <Link
          href="/login"
          className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-hover"
        >
          Iniciar sesión
        </Link>
      </header>
      <section className="mx-auto max-w-5xl px-6 py-16">
        <p className="text-xs tracking-[0.25em] text-muted uppercase">Uso interno</p>
        <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight text-ink">
          Familias, contratos y facturas de transporte escolar, en un solo sitio.
        </h1>
        <p className="mt-4 max-w-xl text-muted">
          El equipo revisa lo que llega por correo. Las familias consultan solo lo ya publicado.
          Nada de datos de menores en un tablero que no toca.
        </p>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {[
            {
              title: 'Familias y contratos',
              body: 'Ficha de cada familia: alumnos, servicio contratado, notas internas y tareas.',
            },
            {
              title: 'Cola de revisión',
              body: 'Kanban por estado. Se asigna familia y se publica; hasta entonces el padre no la ve.',
            },
            {
              title: 'Proveedores',
              body: 'Las facturas de combustible, taller y seguros viven en su propio tablero.',
            },
          ].map((item) => (
            <article
              key={item.title}
              className="rounded-xl border border-line bg-paper p-5 shadow-sm"
            >
              <h2 className="font-medium text-ink">{item.title}</h2>
              <p className="mt-2 text-sm text-muted">{item.body}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
