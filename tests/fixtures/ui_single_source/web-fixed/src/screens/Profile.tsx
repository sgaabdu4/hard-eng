export function Profile() {
  const wide = window.matchMedia("(min-width: 768px)");
  return (
    <section>
      <a href="#feed">Skip</a>
      <svg>
        <use href="#icon-add" />
        <rect fill="url(#fade)" />
      </svg>
      <img sizes="(min-width: 768px) 50vw, 100vw" />
      <p className="bg-brand p-3 rounded-lg text-sm">a</p>
      <div className="w-[100%] h-[100dvh] bg-[url(/a.png)] grid-cols-[1fr_2fr] w-[calc(100%-var(--gutter))]" />
      <p style={{ padding: "var(--spacing-3)", color: "rgb(var(--brand-rgb))" }}>b</p>
      <p className="leading-[1.1] tracking-[0.14em]">c</p>
      {wide.matches ? "wide" : "narrow"}
    </section>
  );
}
