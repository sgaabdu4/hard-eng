export function Button({ label }: { label: string }) {
  return <button type="button">{label}</button>;
}

export function Modal() {
  return <dialog open />;
}
