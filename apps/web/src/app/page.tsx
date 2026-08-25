export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-semibold">CRM Transporte</h1>
      <p className="text-sm text-neutral-500">
        <a href="/login" className="underline">
          Iniciar sesión
        </a>
      </p>
    </main>
  );
}
