/**
 * Carga de datos con estado de carga y error.
 *
 * Es deliberadamente pequeño en vez de traer una librería de data fetching: la
 * app tiene ocho pantallas con necesidades simples, y cada dependencia nueva es
 * algo más que mantener y que justificar en el informe. Lo único que hay que
 * cuidar acá es que una respuesta que llega tarde no pise el estado de una
 * pantalla que el usuario ya abandonó — de ahí el `cancelado`.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";

export interface EstadoCarga<T> {
  datos: T | undefined;
  cargando: boolean;
  error: Error | undefined;
  recargar: () => void;
}

export function useApi<T>(ruta: string | null): EstadoCarga<T> {
  const [datos, setDatos] = useState<T>();
  const [cargando, setCargando] = useState(ruta !== null);
  const [error, setError] = useState<Error>();
  const [version, setVersion] = useState(0);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (ruta === null) {
      setCargando(false);
      return;
    }

    let cancelado = false;
    setCargando(true);
    setError(undefined);

    api
      .get<T>(ruta)
      .then((resultado) => {
        if (!cancelado) setDatos(resultado);
      })
      .catch((e: Error) => {
        if (!cancelado) setError(e);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [ruta, version]);

  return { datos, cargando, error, recargar };
}

/**
 * Para acciones que el usuario dispara (enviar el cuestionario, validar un
 * fragmento, generar una simulación). Separado de `useApi` porque una mutación
 * no debe correr sola al montar la pantalla.
 */
export function useAccion<Args extends unknown[], T>(
  accion: (...args: Args) => Promise<T>,
) {
  const [enProceso, setEnProceso] = useState(false);
  const [error, setError] = useState<Error>();

  const ejecutar = useCallback(
    async (...args: Args): Promise<T | undefined> => {
      setEnProceso(true);
      setError(undefined);
      try {
        return await accion(...args);
      } catch (e) {
        setError(e as Error);
        return undefined;
      } finally {
        setEnProceso(false);
      }
    },
    // `accion` suele venir como función inline; se omite a propósito de las
    // dependencias para no recrear `ejecutar` en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  return { ejecutar, enProceso, error, limpiarError: () => setError(undefined) };
}
