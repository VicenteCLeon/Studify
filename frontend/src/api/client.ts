/**
 * Cliente HTTP de la API.
 *
 * Dos decisiones que no son de estilo:
 *
 * 1. **`credentials: "same-origin"`.** La sesión —tanto la del estudiante como
 *    la del docente— vive en una cookie `httpOnly` firmada con HMAC
 *    (`web/sesion.py`). No hay ningún token en `localStorage` que el código
 *    pueda leer, que es justamente lo que hace que un XSS no pueda robar la
 *    sesión. Este cliente nunca guarda credenciales.
 *
 * 2. **El error del backend se propaga con su mensaje.** FastAPI responde
 *    `{"detail": "..."}` con mensajes ya escritos en español y pensados para
 *    quien los va a leer (por ejemplo, los de `_explicar_fallo`). Reemplazarlos
 *    por un "algo salió mal" genérico perdería información que el backend se
 *    tomó el trabajo de producir.
 */

export class ErrorApi extends Error {
  constructor(
    readonly status: number,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }
}

/** `true` cuando la sesión venció o nunca existió. */
export function esNoAutenticado(error: unknown): boolean {
  return error instanceof ErrorApi && (error.status === 401 || error.status === 403);
}

async function extraerMensaje(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    const detalle = cuerpo?.detail;
    if (typeof detalle === "string") return detalle;
    // 422 de Pydantic: lista de errores por campo.
    if (Array.isArray(detalle)) {
      return detalle
        .map((e: { loc?: unknown[]; msg?: string }) => {
          const campo = Array.isArray(e.loc) ? e.loc.slice(1).join(".") : "";
          return campo ? `${campo}: ${e.msg}` : e.msg;
        })
        .join("; ");
    }
  } catch {
    // Respuesta sin cuerpo JSON (502 de un proxy, por ejemplo).
  }
  return `La petición falló (${respuesta.status}).`;
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(ruta, {
    ...init,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await extraerMensaje(respuesta));
  }

  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

export const api = {
  get: <T>(ruta: string) => pedir<T>(ruta),

  post: <T>(ruta: string, cuerpo?: unknown) =>
    pedir<T>(ruta, {
      method: "POST",
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    }),

  patch: <T>(ruta: string, cuerpo?: unknown) =>
    pedir<T>(ruta, {
      method: "PATCH",
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    }),

  del: <T>(ruta: string) => pedir<T>(ruta, { method: "DELETE" }),

  /** Subida de archivos: `FormData` va sin `Content-Type` para que el navegador
   *  ponga el `boundary` del multipart. */
  subir: <T>(ruta: string, datos: FormData) =>
    pedir<T>(ruta, { method: "POST", body: datos }),
};
