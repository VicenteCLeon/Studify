/**
 * Visor de microcápsulas. Porta `student/viewer.html`, `_feedback.html` y
 * `capsula_no_disponible.html`, más la lógica de `get_viewer`/`submit_activity`.
 *
 * El parámetro de la ruta es el **objetivo de aprendizaje**, no una cápsula: el
 * estudiante elige un tema y el sistema decide si hay que generar o si ya existe
 * una cápsula con la misma huella. Toda esa política —caché en dos niveles,
 * versionado— vive en `POST /api/capsulas`; acá solo se muestra lo que devuelve.
 *
 * **La corrección del quiz se hace en el servidor.** `indice_correcta` no llega
 * nunca a este componente: se manda la alternativa elegida a
 * `POST /api/capsulas/{id}/responder` y el servidor contesta si acertó. Si la
 * clave viajara al cliente, estaría en la pestaña de red antes de contestar.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ErrorApi } from "../../api/client";
import type { Capsula, ResultadoActividad } from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { CapsulaVista } from "../../components/CapsulaVista";
import { useApi } from "../../hooks/useApi";

/**
 * Traduce el error del endpoint a algo que el estudiante entienda.
 *
 * Los tres casos son distintos y conviene que se distingan en pantalla: falta la
 * credencial (problema de configuración), falta material curado (problema del
 * docente) o el modelo no logró producir una cápsula válida en los reintentos
 * (problema de generación, y una métrica del criterio de término de la Fase 3).
 */
function explicarFallo(error: Error): { titulo: string; mensaje: string } {
  const status = error instanceof ErrorApi ? error.status : 0;
  if (status === 503) {
    return {
      titulo: "Falta configurar el modelo de lenguaje",
      mensaje:
        "El sistema no tiene credencial del LLM (LLM_API_KEY en el .env), así " +
        "que no puede generar cápsulas nuevas. Las que ya estén generadas se " +
        "siguen mostrando.",
    };
  }
  if (status === 502) {
    return {
      titulo: "El modelo no logró una cápsula válida",
      mensaje:
        "La respuesta no pasó la validación en ninguno de los reintentos. " +
        "Puedes volver a intentarlo; si se repite, hay que revisar el prompt o " +
        "el material del tema.",
    };
  }
  if (status === 422) {
    return {
      titulo: "Este tema todavía no tiene material curado",
      mensaje:
        "No hay fragmentos validados asociados a este objetivo, y el sistema no " +
        "genera contenido sin material institucional que lo respalde.",
    };
  }
  return { titulo: "No se pudo preparar la cápsula", mensaje: error.message };
}

export function Visor() {
  const { idObjetivo } = useParams<{ idObjetivo: string }>();
  const { datos: sesion, cargando: cargandoSesion } =
    useApi<{ id_estudiante: number | null }>("/api/sesion");

  const [capsula, setCapsula] = useState<Capsula>();
  const [fallo, setFallo] = useState<Error>();
  const [generando, setGenerando] = useState(true);

  const idEstudiante = sesion?.id_estudiante ?? null;

  // La generación es un POST (crea una fila), así que no cabe en `useApi`, que
  // está pensado para lecturas. `cancelado` evita que una respuesta que llega
  // tarde —la generación tarda 5-6 s contra el modelo real— pise el estado de
  // una pantalla que el estudiante ya abandonó.
  useEffect(() => {
    if (idEstudiante === null || !idObjetivo) return;

    let cancelado = false;
    setGenerando(true);
    setFallo(undefined);

    api
      .post<Capsula>("/api/capsulas", {
        id_estudiante: idEstudiante,
        id_objetivo: Number(idObjetivo),
      })
      .then((resultado) => {
        if (!cancelado) setCapsula(resultado);
      })
      .catch((e: Error) => {
        if (!cancelado) setFallo(e);
      })
      .finally(() => {
        if (!cancelado) setGenerando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [idEstudiante, idObjetivo]);

  if (cargandoSesion) return <Cargando />;

  if (idEstudiante === null) {
    return (
      <NoDisponible
        titulo="Necesitas responder el cuestionario"
        mensaje={
          "Tu perfil VARK es lo que decide cómo se arma la cápsula, así que " +
          "hace falta antes de estudiar un tema."
        }
      />
    );
  }

  if (fallo) {
    const { titulo, mensaje } = explicarFallo(fallo);
    return <NoDisponible titulo={titulo} mensaje={mensaje} />;
  }

  if (generando || !capsula) {
    return (
      <Cargando texto="Preparando tu microcápsula… (puede tardar unos segundos si hay que generarla)" />
    );
  }

  return (
    <>
      <div className="mb-4">
        <Link to="/catalogo" className="text-muted">
          ← Volver al catálogo
        </Link>
      </div>
      <CapsulaVista
        capsula={capsula}
        codigoObjetivo={capsula.objetivo?.codigo_objetivo ?? `OA #${capsula.id_objetivo}`}
        asignatura={capsula.objetivo?.asignatura ?? ""}
        unidad={capsula.objetivo?.unidad ?? ""}
        insignia={
          capsula.origen === "generada" ? "Generada para ti" : "Recuperada de caché"
        }
      >
        <FormularioActividad capsula={capsula} />
      </CapsulaVista>
    </>
  );
}

/** La actividad de cierre y su retroalimentación. Porta `_feedback.html`. */
function FormularioActividad({ capsula }: { capsula: Capsula }) {
  const esOpcionMultiple = capsula.actividad.tipo === "quiz_mc";
  const [elegida, setElegida] = useState<number>();
  const [resultado, setResultado] = useState<ResultadoActividad>();
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function revisar(evento: React.FormEvent) {
    evento.preventDefault();
    if (esOpcionMultiple && elegida === undefined) {
      setError("Selecciona una alternativa antes de revisar.");
      return;
    }
    setError(undefined);
    setEnviando(true);
    try {
      setResultado(
        await api.post<ResultadoActividad>(
          `/api/capsulas/${capsula.id_capsula}/responder`,
          { alternativa: esOpcionMultiple ? elegida : null },
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <form onSubmit={(e) => void revisar(e)}>
        {esOpcionMultiple ? (
          <div className="radio-group mb-6">
            {capsula.actividad.alternativas.map((alternativa, i) => (
              <label
                key={i}
                className="radio-option"
                style={{ backgroundColor: "var(--bg-surface)" }}
              >
                <input
                  type="radio"
                  name="answer"
                  checked={elegida === i}
                  onChange={() => setElegida(i)}
                />
                <span>{alternativa}</span>
              </label>
            ))}
          </div>
        ) : (
          <div className="form-group">
            <textarea
              className="form-control"
              rows={4}
              placeholder="Escribe aquí tu resolución antes de contrastarla."
            />
          </div>
        )}

        <div className="flex items-center gap-4">
          <button type="submit" className="btn btn-primary" disabled={enviando}>
            {enviando
              ? "Revisando…"
              : esOpcionMultiple
                ? "Revisar Respuesta"
                : "Ver la respuesta esperada"}
          </button>
        </div>
      </form>

      <div className="mt-4">
        {error && <Alerta estado="error">{error}</Alerta>}
        {resultado && (
          <Alerta
            estado={
              resultado.estado === "ok"
                ? "ok"
                : resultado.estado === "error"
                  ? "error"
                  : "info"
            }
          >
            <strong>{resultado.titulo}</strong>
            {resultado.correcta && (
              <div className="mt-2">La correcta era: «{resultado.correcta}».</div>
            )}
            {resultado.retroalimentacion && (
              <div className="mt-2">{resultado.retroalimentacion}</div>
            )}
          </Alerta>
        )}
      </div>
    </>
  );
}

function NoDisponible({ titulo, mensaje }: { titulo: string; mensaje: string }) {
  return (
    <>
      <div className="mb-4">
        <Link to="/catalogo" className="text-muted">
          ← Volver al catálogo
        </Link>
      </div>
      <div className="card text-center" style={{ maxWidth: "640px", margin: "0 auto" }}>
        <h1 className="mb-4">{titulo}</h1>
        <p className="text-muted mb-8">{mensaje}</p>
        <div className="flex justify-center gap-4">
          <Link to="/catalogo" className="btn btn-primary">
            Elegir otro tema
          </Link>
          <Link to="/docente/curacion" className="btn btn-outline">
            Panel de curación
          </Link>
        </div>
      </div>
    </>
  );
}
