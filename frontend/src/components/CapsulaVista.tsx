/**
 * La microcápsula renderizada. Porta `student/_capsula.html`.
 *
 * La usan dos pantallas con contextos **opuestos**, y esa oposición es todo lo
 * que decide `esSimulacion`:
 *
 * - el **visor del estudiante**, donde se responde la actividad y donde
 *   `indice_correcta`/`retroalimentacion` no llegan siquiera desde el servidor;
 * - el **simulador del docente**, que necesita exactamente lo contrario: ver la
 *   alternativa correcta y la retroalimentación para juzgar si la actividad
 *   evalúa el objetivo, sin responder nada (la cápsula simulada no se persiste,
 *   así que no hay `id_capsula` contra el cual corregir).
 */

import type {
  Actividad,
  BloqueContenido,
  CuerpoBloque,
  Fuente,
} from "../api/types";

/** Los siete pasos que se muestran como bloques: representación + ejemplo. */
export interface CapsulaRenderizable {
  titulo: string;
  objetivo_aprendizaje: string;
  activacion: string;
  concepto_central: string;
  representacion_adaptativa: BloqueContenido[];
  ejemplo: BloqueContenido;
  actividad: Actividad;
  fuentes: Fuente[];
}

interface Props {
  capsula: CapsulaRenderizable;
  codigoObjetivo: string;
  asignatura: string;
  unidad: string;
  /** La insignia de la derecha: origen de la cápsula o el perfil simulado. */
  insignia: string;
  esSimulacion?: boolean;
  /** El formulario de respuesta; solo lo pasa el visor del estudiante. */
  children?: React.ReactNode;
}

/**
 * Qué forma tiene el `cuerpo` de un bloque.
 *
 * Es el equivalente de `_preparar_bloques` en `web/routers/student.py`: el
 * contrato admite tres formas y decidir cuál es cuál dentro del JSX repartiría
 * lógica de tipos por toda la vista.
 */
type FormaBloque = "texto" | "lista" | "filas";

function formaDe(cuerpo: CuerpoBloque): FormaBloque {
  if (typeof cuerpo === "string") return "texto";
  if (cuerpo.length > 0 && cuerpo.every((fila) => Array.isArray(fila))) return "filas";
  return "lista";
}

function CuerpoDelBloque({ bloque }: { bloque: BloqueContenido }) {
  const forma = formaDe(bloque.cuerpo);

  if (forma === "texto") {
    return <p>{bloque.cuerpo as string}</p>;
  }

  if (forma === "lista") {
    const elementos = bloque.cuerpo as string[];
    // `lista_pasos` va numerada: el orden es parte del contenido, no estilo.
    const Lista = bloque.tipo === "lista_pasos" ? "ol" : "ul";
    return (
      <Lista className="lista-bloque">
        {elementos.map((elemento, i) => (
          <li key={i}>{elemento}</li>
        ))}
      </Lista>
    );
  }

  const filas = bloque.cuerpo as string[][];

  if (bloque.tipo === "glosario") {
    return (
      <dl className="glosario">
        {filas.map((fila, i) => (
          <div key={i}>
            <dt>{fila[0]}</dt>
            <dd>{fila.slice(1).join(" ")}</dd>
          </div>
        ))}
      </dl>
    );
  }

  const [encabezados, ...cuerpo] = filas;
  return (
    <div className="table-container">
      <table className="table">
        {encabezados && (
          <thead>
            <tr>
              {encabezados.map((celda, i) => (
                <th key={i}>{celda}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {cuerpo.map((fila, i) => (
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

export function CapsulaVista({
  capsula,
  codigoObjetivo,
  asignatura,
  unidad,
  insignia,
  esSimulacion = false,
  children,
}: Props) {
  // Los bloques en orden de lectura: la representación adaptativa y después el
  // ejemplo. Es lo que hace `bloques_legibles()` en el backend.
  const bloques = [...capsula.representacion_adaptativa, capsula.ejemplo];

  return (
    <div className="card" style={{ maxWidth: "900px", margin: "0 auto" }}>
      <div className="capsule-header">
        <h1 className="mb-2">{capsula.titulo}</h1>
        <p className="text-muted mb-4">{capsula.objetivo_aprendizaje}</p>
        <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
          <span className="badge badge-primary">{codigoObjetivo}</span>
          <span className="badge badge-success">
            {asignatura} · {unidad}
          </span>
          <span className="badge badge-warning">{insignia}</span>
        </div>
      </div>

      {/* Pasos 2 y 3 de la estructura pedagógica. Van fuera del recorrido de
          bloques porque no son bloques tipados: son campos propios del contrato,
          y que la activación aparezca siempre antes del concepto es parte del
          diseño, no algo que decida el orden en que el modelo devolvió una lista. */}
      <div className="capsule-activation">
        <p className="paso-etiqueta">Para partir</p>
        <p className="pregunta-activacion">{capsula.activacion}</p>
      </div>

      <div className="capsule-content">
        <div className="bloque bloque-concepto">
          <h3 className="mb-2">Concepto central</h3>
          <p>{capsula.concepto_central}</p>
        </div>

        {bloques.map((bloque, i) => (
          <div key={i} className={`bloque bloque-${bloque.tipo}`}>
            {bloque.encabezado && <h3 className="mb-2">{bloque.encabezado}</h3>}
            <CuerpoDelBloque bloque={bloque} />
          </div>
        ))}
      </div>

      <div className="capsule-activity" id="activity-container">
        <h3 className="mb-4">Actividad de Cierre</h3>
        <p className="mb-4">{capsula.actividad.pregunta}</p>

        {esSimulacion ? (
          <ActividadRevelada actividad={capsula.actividad} />
        ) : (
          children
        )}
      </div>

      <div className="fuentes mt-8">
        <h3 className="mb-2 text-lg">Fuentes</h3>
        <p className="text-sm text-muted mb-2">
          Esta cápsula se construyó únicamente con estos fragmentos del material
          institucional. El sistema verifica cada cita contra la base de datos.
        </p>
        <ul className="lista-fuentes">
          {capsula.fuentes.map((fuente) => (
            <li key={fuente.id_fragmento}>
              <span className="badge badge-primary">#{fuente.id_fragmento}</span>{" "}
              {fuente.documento}
              {fuente.pagina ? `, p. ${fuente.pagina}` : ""}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/**
 * La actividad con la clave a la vista. **Solo para el simulador del docente.**
 *
 * El estudiante nunca llega acá: su cápsula viene del servidor sin
 * `indice_correcta` ni `retroalimentacion`, así que ni siquiera habría qué
 * mostrar. Es el mismo cuidado que tiene el backend, expresado en el cliente.
 */
function ActividadRevelada({ actividad }: { actividad: Actividad }) {
  return (
    <>
      {actividad.tipo === "quiz_mc" && (
        <div className="radio-group mb-4">
          {actividad.alternativas.map((alternativa, i) => (
            <label
              key={i}
              className="radio-option"
              style={{ backgroundColor: "var(--bg-surface)" }}
            >
              <input
                type="radio"
                disabled
                checked={i === actividad.indice_correcta}
                readOnly
              />
              <span>{alternativa}</span>
            </label>
          ))}
        </div>
      )}
      <div className="alerta alerta-info" role="status">
        <strong>
          {actividad.tipo === "quiz_mc"
            ? "Retroalimentación que verá el estudiante al acertar o fallar"
            : "Respuesta esperada"}
        </strong>
        <div className="mt-2">{actividad.retroalimentacion}</div>
      </div>
    </>
  );
}
