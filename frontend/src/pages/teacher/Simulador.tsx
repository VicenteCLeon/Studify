/**
 * Simulador VARK. Porta `teacher/simulator.html` y `teacher/_comparacion.html`.
 *
 * Dos modos, como en la plantilla:
 *
 * - **un perfil a la vez**, que muestra la cápsula completa con el mismo
 *   componente que ve el estudiante pero con la clave del quiz a la vista: el
 *   docente vino justamente a revisar si la actividad evalúa el objetivo;
 * - **los cuatro lado a lado**, que es el criterio de término de la Fase 3
 *   («si no se distinguen entre sí, la adaptación no está funcionando»). Acá se
 *   muestra un resumen y no la cápsula entera: cuatro cápsulas completas una
 *   junto a otra serían ilegibles, y lo que hay que juzgar es la diferencia
 *   **estructural** entre columnas.
 */

import { useState } from "react";

import { api } from "../../api/client";
import type {
  BloqueContenido,
  ColumnaSimulacion,
  CuerpoBloque,
  Objetivo,
} from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { CapsulaVista } from "../../components/CapsulaVista";
import { useApi } from "../../hooks/useApi";

const CANALES = [
  { valor: "V", etiqueta: "Visual (100%)" },
  { valor: "A", etiqueta: "Aural (100%)" },
  { valor: "R", etiqueta: "Lecto/Escritura (100%)" },
  { valor: "K", etiqueta: "Kinestésico (100%)" },
];

export function Simulador() {
  const { datos: objetivos, cargando } = useApi<Objetivo[]>("/api/objetivos");

  const [idObjetivoUno, setIdObjetivoUno] = useState("");
  const [canal, setCanal] = useState("");
  const [idObjetivoCuatro, setIdObjetivoCuatro] = useState("");

  const [columnas, setColumnas] = useState<ColumnaSimulacion[]>();
  const [temaComparado, setTemaComparado] = useState<string>();
  const [error, setError] = useState<string>();
  const [generando, setGenerando] = useState(false);

  function temaDe(id: string): string {
    const objetivo = objetivos?.find((o) => String(o.id_objetivo) === id);
    return objetivo?.tema ?? "";
  }

  async function generarUno(evento: React.FormEvent) {
    evento.preventDefault();
    setError(undefined);
    setGenerando(true);
    setColumnas(undefined);
    setTemaComparado(undefined);
    try {
      const columna = await api.post<ColumnaSimulacion>("/api/simulador/generar", {
        id_objetivo: Number(idObjetivoUno),
        canal,
      });
      setColumnas([columna]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerando(false);
    }
  }

  async function compararCuatro(evento: React.FormEvent) {
    evento.preventDefault();
    setError(undefined);
    setGenerando(true);
    setColumnas(undefined);
    try {
      const resultado = await api.post<ColumnaSimulacion[]>(
        "/api/simulador/comparar",
        { id_objetivo: Number(idObjetivoCuatro) },
      );
      setColumnas(resultado);
      setTemaComparado(temaDe(idObjetivoCuatro));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerando(false);
    }
  }

  if (cargando) return <Cargando />;

  const opciones = objetivos ?? [];

  return (
    <>
      <div className="mb-8">
        <h1 className="mb-2">Simulador de Generación (VARK)</h1>
        <p className="text-muted">
          Elige un Tema Curricular y un Perfil de Aprendizaje dominante. El
          sistema generará una cápsula al vuelo para que puedas evaluar la calidad
          de la adaptación pedagógica antes de habilitarla para los alumnos.
        </p>
      </div>

      <div className="card mb-8">
        <h3 className="mb-2">Un perfil a la vez</h3>
        <form
          onSubmit={(e) => void generarUno(e)}
          className="flex items-center gap-4"
          style={{ flexWrap: "wrap" }}
        >
          <select
            className="form-control"
            required
            style={{ maxWidth: "300px" }}
            value={idObjetivoUno}
            onChange={(e) => setIdObjetivoUno(e.target.value)}
          >
            <option value="">Selecciona un Tema...</option>
            {opciones.map((objetivo) => (
              <option key={objetivo.id_objetivo} value={objetivo.id_objetivo}>
                {objetivo.asignatura} - {objetivo.tema}
              </option>
            ))}
          </select>

          <select
            className="form-control"
            required
            style={{ maxWidth: "200px" }}
            value={canal}
            onChange={(e) => setCanal(e.target.value)}
          >
            <option value="">Perfil a simular...</option>
            {CANALES.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.etiqueta}
              </option>
            ))}
          </select>

          <button type="submit" className="btn btn-primary" disabled={generando}>
            {generando ? "Generando…" : "Generar Cápsula"}
          </button>
        </form>
      </div>

      <div className="card mb-8">
        <h3 className="mb-2">Los cuatro perfiles, lado a lado</h3>
        <p className="text-muted text-sm mb-4">
          Genera V, A, R y K sobre el mismo tema para juzgar de un vistazo si la
          adaptación se nota entre perfiles. Son cuatro llamadas al modelo: tarda
          más que generar uno solo.
        </p>
        <form
          onSubmit={(e) => void compararCuatro(e)}
          className="flex items-center gap-4"
          style={{ flexWrap: "wrap" }}
        >
          <select
            className="form-control"
            required
            style={{ maxWidth: "300px" }}
            value={idObjetivoCuatro}
            onChange={(e) => setIdObjetivoCuatro(e.target.value)}
          >
            <option value="">Selecciona un Tema...</option>
            {opciones.map((objetivo) => (
              <option key={objetivo.id_objetivo} value={objetivo.id_objetivo}>
                {objetivo.asignatura} - {objetivo.tema}
              </option>
            ))}
          </select>

          <button type="submit" className="btn btn-outline" disabled={generando}>
            {generando ? "Generando 4 cápsulas…" : "Comparar los 4 perfiles"}
          </button>
        </form>
      </div>

      {error && <Alerta estado="error">{error}</Alerta>}
      {generando && (
        <Cargando texto="Generando contra el modelo real… puede tardar varios segundos." />
      )}

      {columnas && columnas.length === 1 && (
        <ColumnaCompleta columna={columnas[0]!} objetivos={opciones} id={idObjetivoUno} />
      )}
      {columnas && columnas.length > 1 && (
        <Comparacion columnas={columnas} tema={temaComparado ?? ""} />
      )}
    </>
  );
}

/** Un solo canal: la cápsula entera, con la clave del quiz visible. */
function ColumnaCompleta({
  columna,
  objetivos,
  id,
}: {
  columna: ColumnaSimulacion;
  objetivos: Objetivo[];
  id: string;
}) {
  if (columna.error) return <Alerta estado="error">{columna.error}</Alerta>;
  if (!columna.capsula) return null;

  const objetivo = objetivos.find((o) => String(o.id_objetivo) === id);

  return (
    <CapsulaVista
      capsula={columna.capsula}
      codigoObjetivo={objetivo?.codigo_objetivo ?? ""}
      asignatura={objetivo?.asignatura ?? ""}
      unidad={objetivo?.unidad ?? ""}
      insignia={`Simulación · perfil ${columna.nombre_canal} 100%`}
      esSimulacion
    />
  );
}

/**
 * Los cuatro perfiles en columnas. Porta `_comparacion.html`.
 *
 * Deliberadamente **no** reutiliza `CapsulaVista`: lo que se juzga acá es la
 * diferencia estructural entre columnas (qué bloques trae cada una, con qué tipo
 * de actividad cierra), no leer cuatro cápsulas completas.
 */
function Comparacion({
  columnas,
  tema,
}: {
  columnas: ColumnaSimulacion[];
  tema: string;
}) {
  return (
    <>
      <div className="mb-4">
        <h2 className="mb-1">Comparación para «{tema}»</h2>
        <p className="text-muted text-sm">
          Perfil puro (100% en un solo canal) para cada columna, mismo material.
          Si dos columnas se parecen demasiado, la adaptación no está
          diferenciando ese par de perfiles.
        </p>
      </div>

      <div className="grid-comparacion">
        {columnas.map((columna) => (
          <div
            key={columna.canal}
            className="card comparacion-columna"
            style={{ borderTop: `4px solid ${columna.color_canal}` }}
          >
            <span
              className="badge mb-4"
              style={{
                backgroundColor: `${columna.color_canal}26`,
                color: columna.color_canal,
              }}
            >
              {columna.nombre_canal} · 100%
            </span>

            {columna.error || !columna.capsula ? (
              <p className="alerta alerta-error">{columna.error}</p>
            ) : (
              <ResumenColumna columna={columna} />
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function ResumenColumna({ columna }: { columna: ColumnaSimulacion }) {
  const capsula = columna.capsula!;
  const bloques = [...capsula.representacion_adaptativa, capsula.ejemplo];

  return (
    <>
      <h3 className="mb-4">{capsula.titulo}</h3>

      <p className="paso-etiqueta">Para partir</p>
      <p className="text-sm mb-4">{capsula.activacion}</p>

      <p className="paso-etiqueta">Concepto central</p>
      <p className="text-sm mb-4">{capsula.concepto_central}</p>

      <p className="paso-etiqueta">Representación adaptativa + ejemplo</p>
      <div className="flex gap-2 mb-2" style={{ flexWrap: "wrap" }}>
        {bloques.map((bloque, i) => (
          <span key={i} className="badge badge-primary">
            {bloque.tipo.replace("_", " ")}
          </span>
        ))}
      </div>

      {bloques.map((bloque, i) => (
        <div key={i} className="mb-4">
          {bloque.encabezado && (
            <strong className="text-sm">{bloque.encabezado}</strong>
          )}
          <CuerpoResumido bloque={bloque} />
        </div>
      ))}

      <p className="paso-etiqueta">Actividad de cierre</p>
      <span className="badge badge-warning mb-2">{capsula.actividad.tipo}</span>
      <p className="text-sm mb-4">{capsula.actividad.pregunta}</p>

      <p className="text-sm text-muted">
        {columna.palabras} palabras · {capsula.fuentes.length} fuente(s)
      </p>
    </>
  );
}

function CuerpoResumido({ bloque }: { bloque: BloqueContenido }) {
  const cuerpo: CuerpoBloque = bloque.cuerpo;

  if (typeof cuerpo === "string") return <p className="text-sm">{cuerpo}</p>;

  const esMatriz = cuerpo.length > 0 && cuerpo.every((f) => Array.isArray(f));
  if (esMatriz) {
    return (
      <div className="table-container">
        <table className="table text-sm">
          <tbody>
            {(cuerpo as string[][]).map((fila, i) => (
              <tr key={i}>
                {fila.map((celda, j) => (
                  <td key={j}>{celda}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const Lista = bloque.tipo === "lista_pasos" ? "ol" : "ul";
  return (
    <Lista className="text-sm lista-bloque">
      {(cuerpo as string[]).map((elemento, i) => (
        <li key={i}>{elemento}</li>
      ))}
    </Lista>
  );
}
