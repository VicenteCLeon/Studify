/** Aviso de estado. Porta `teacher/_aviso.html` y los `div.alerta` sueltos. */

interface Props {
  estado: "ok" | "error" | "info";
  children: React.ReactNode;
}

const CLASE = {
  ok: "alerta alerta-ok",
  error: "alerta alerta-error",
  info: "alerta alerta-info",
} as const;

export function Alerta({ estado, children }: Props) {
  return (
    <div className={CLASE[estado]} role={estado === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** El estado de carga que antes daba el `htmx-indicator`. */
export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return <p className="text-muted">{texto}</p>;
}
