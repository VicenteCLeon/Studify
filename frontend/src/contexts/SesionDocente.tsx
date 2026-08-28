/**
 * Estado de la sesión del docente, compartido por toda la app.
 *
 * Va en un contexto y no en cada pantalla por la misma razón por la que el
 * backend inyecta `es_docente` con un procesador de contexto de Jinja
 * (`web/deps.py`): la cabecera es compartida por las dos caras de la aplicación,
 * y si cada pantalla resolviera por su cuenta si hay sesión, cualquiera que lo
 * olvidara le mostraría al docente conectado la barra del estudiante.
 *
 * La sesión **no se guarda acá**: vive en la cookie `httpOnly` firmada que emite
 * el servidor. Esto solo recuerda la respuesta de `GET /api/docente/sesion` para
 * no preguntar en cada render.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "../api/client";
import type { SesionDocente } from "../api/types";

interface Valor {
  autenticado: boolean;
  /** `false` si `TEACHER_PASSWORD` quedó vacía: el panel está cerrado para todos. */
  configurado: boolean;
  cargando: boolean;
  refrescar: () => Promise<void>;
  entrar: (usuario: string, clave: string) => Promise<void>;
  salir: () => Promise<void>;
}

const Contexto = createContext<Valor | null>(null);

export function ProveedorSesionDocente({ children }: { children: React.ReactNode }) {
  const [estado, setEstado] = useState<SesionDocente>({
    autenticado: false,
    configurado: true,
  });
  const [cargando, setCargando] = useState(true);

  const refrescar = useCallback(async () => {
    try {
      setEstado(await api.get<SesionDocente>("/api/docente/sesion"));
    } catch {
      // Si la consulta falla, lo seguro es asumir que no hay sesión: el
      // servidor va a rechazar igual cualquier ruta protegida.
      setEstado({ autenticado: false, configurado: true });
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void refrescar();
  }, [refrescar]);

  const entrar = useCallback(async (usuario: string, clave: string) => {
    // El error se deja propagar: la pantalla de login necesita el mensaje del
    // servidor para distinguir «clave incorrecta» de «panel sin configurar» o
    // de «demasiados intentos».
    setEstado(await api.post<SesionDocente>("/api/docente/login", { usuario, clave }));
  }, []);

  const salir = useCallback(async () => {
    setEstado(await api.post<SesionDocente>("/api/docente/logout"));
  }, []);

  const valor = useMemo(
    () => ({ ...estado, cargando, refrescar, entrar, salir }),
    [estado, cargando, refrescar, entrar, salir],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSesionDocente(): Valor {
  const valor = useContext(Contexto);
  if (valor === null) {
    throw new Error("useSesionDocente debe usarse dentro de ProveedorSesionDocente");
  }
  return valor;
}
