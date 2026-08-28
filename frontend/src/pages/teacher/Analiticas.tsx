/**
 * Panel de analíticas. Porta `teacher/analytics.html`.
 *
 * Las tres tarjetas son las que la plantilla tiene hoy: cobertura curricular,
 * rendimiento de los quizzes e historial de cápsulas. `GET /api/analiticas`
 * devuelve además `vark_barras` (el promedio VARK de la cohorte), que la
 * plantilla dejó de mostrar; se deja sin pintar para no agregar una sección que
 * hoy no existe.
 */

import { Link } from "react-router-dom";

import type { Analiticas as DatosAnaliticas, FilaCobertura } from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { useApi } from "../../hooks/useApi";

export function Analiticas() {
  const { datos, cargando, error } = useApi<DatosAnaliticas>("/api/analiticas");

  if (cargando) return <Cargando texto="Calculando las métricas del curso…" />;
  if (error) return <Alerta estado="error">{error.message}</Alerta>;
  if (!datos) return null;

  return (
    <>
      <div className="mb-8">
        <h1 className="mb-2">Panel de Analíticas</h1>
        <p className="text-muted">
          Estadísticas sobre el uso de la plataforma, el rendimiento de los alumnos
          en los mini-quizzes, y el estado de la cobertura curricular.
        </p>
      </div>

      <Cobertura datos={datos} />
      <Rendimiento datos={datos} />
      <Historial datos={datos} />
    </>
  );
}

function Cobertura({ datos }: { datos: DatosAnaliticas }) {
  return (
    <div className="card mb-8">
      <h2 className="text-lg mb-4">Cobertura Curricular (Gaps)</h2>
      <p className="text-muted mb-4">
        Material que el motor puede recuperar hoy para cada tema: fragmentos
        validados cuyo documento no está rechazado. La columna por canal muestra
        si hay recursos del tipo que cada perfil aprovecha; un canal en gris no
        deja al estudiante sin cápsula, pero recibe el mismo texto que todos y la
        adaptación no se nota.
      </p>

      {datos.sin_clasificar > 0 && (
        <div className="mb-4">
          <Alerta estado="info">
            Hay <strong>{datos.sin_clasificar}</strong> fragmento(s) ingeridos sin
            revisar. Ninguno alimenta un tema hasta que los valides:{" "}
            <Link to="/docente/curacion">ir a la bandeja de curación</Link>.
          </Alerta>
        </div>
      )}

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Asignatura</th>
              <th>Tema</th>
              <th>Material recuperable</th>
              <th>Adaptación por canal</th>
            </tr>
          </thead>
          <tbody>
            {datos.cobertura.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-muted">
                  No hay objetivos de aprendizaje cargados.
                </td>
              </tr>
            ) : (
              datos.cobertura.map((fila) => (
                <FilaDeCobertura key={fila.objetivo.id_objetivo} fila={fila} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilaDeCobertura({ fila }: { fila: FilaCobertura }) {
  return (
    <tr>
      <td>{fila.objetivo.asignatura}</td>
      <td>{fila.objetivo.tema}</td>
      <td>
        {fila.estado === "sin_material" ? (
          <span className="badge badge-danger">Falta material</span>
        ) : fila.estado === "escaso" ? (
          <span className="badge badge-warning">
            {fila.total} fragmento(s): escaso
          </span>
        ) : (
          <span className="badge badge-success">{fila.total} fragmentos</span>
        )}
        {fila.tipos.length > 0 && (
          <div className="text-muted text-sm mt-1">
            {fila.tipos.map((t) => `${t.cantidad} ${t.tipo}`).join(" · ")}
          </div>
        )}
      </td>
      <td>
        {fila.total > 0 ? (
          <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
            {fila.canales.map((canal) => (
              <span
                key={canal.canal}
                className={`badge ${canal.degradado ? "badge-warning" : "badge-success"}`}
                title={
                  canal.degradado
                    ? `${canal.nombre}: sin recursos del tipo que este perfil aprovecha, recibirá solo texto`
                    : `${canal.nombre}: ${canal.cantidad} fragmento(s) del tipo preferido`
                }
              >
                {canal.canal}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-muted text-sm">—</span>
        )}
      </td>
    </tr>
  );
}

/** El color del porcentaje: los mismos cortes que usaba la plantilla. */
function colorDeAcierto(porcentaje: number): string {
  if (porcentaje >= 70) return "var(--success)";
  if (porcentaje >= 40) return "var(--warning)";
  return "var(--danger)";
}

function Rendimiento({ datos }: { datos: DatosAnaliticas }) {
  return (
    <div className="card mb-8">
      <h2 className="text-lg mb-4">Métricas de Rendimiento (Quizzes)</h2>
      <p className="text-muted mb-4">
        Aciertos <strong>al primer intento</strong>: el estudiante puede reenviar
        la actividad, y contar los reintentos subiría el porcentaje sin que nadie
        haya entendido más. Si el porcentaje es bajo o hay muchos reintentos,
        considera mejorar el material curado para ese tema.
      </p>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Tema</th>
              <th>Alumnos</th>
              <th>Respuestas (1er intento)</th>
              <th>Aciertos</th>
              <th>Acierto al 1er intento</th>
              <th>Reintentos</th>
            </tr>
          </thead>
          <tbody>
            {datos.rendimiento.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted">
                  Aún no hay respuestas de los alumnos.
                </td>
              </tr>
            ) : (
              datos.rendimiento.map((fila) => (
                <tr key={fila.tema}>
                  <td>{fila.tema}</td>
                  <td>{fila.alumnos}</td>
                  <td>
                    {fila.primeras}
                    {fila.abiertas > 0 && (
                      <span className="text-muted text-sm">
                        {" "}
                        (+{fila.abiertas} abiertas)
                      </span>
                    )}
                  </td>
                  <td>{fila.aciertos}</td>
                  <td>
                    {fila.porcentaje === null ? (
                      <span className="text-muted text-sm">sin quiz corregible</span>
                    ) : (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                        }}
                      >
                        <div className="progress-container" style={{ height: "8px" }}>
                          <div
                            className="progress-bar"
                            style={{
                              width: `${fila.porcentaje}%`,
                              backgroundColor: colorDeAcierto(fila.porcentaje),
                            }}
                          />
                        </div>
                        <span
                          className="text-sm"
                          style={{ minWidth: "40px", textAlign: "right" }}
                        >
                          {fila.porcentaje}%
                        </span>
                      </div>
                    )}
                  </td>
                  <td>{fila.reintentos}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Historial({ datos }: { datos: DatosAnaliticas }) {
  return (
    <div className="card">
      <h2 className="text-lg mb-4">Historial Reciente de Cápsulas</h2>
      <div className="table-container">
        <table className="table text-sm">
          <thead>
            <tr>
              <th>ID</th>
              <th>Fecha</th>
              <th>Estudiante</th>
              <th>Tema Generado</th>
              <th>Modelo LLM</th>
            </tr>
          </thead>
          <tbody>
            {datos.capsulas.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-muted">
                  No se han generado cápsulas.
                </td>
              </tr>
            ) : (
              datos.capsulas.map((capsula) => (
                <tr key={capsula.id_capsula}>
                  <td>#{capsula.id_capsula}</td>
                  <td>{formatearFecha(capsula.fecha_generacion)}</td>
                  <td>Estudiante #{capsula.id_estudiante}</td>
                  <td>{capsula.titulo}</td>
                  <td>{capsula.modelo_llm ?? "Desconocido"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** `dd-mm-aaaa hh:mm`, el mismo formato que usaba `strftime` en la plantilla. */
function formatearFecha(iso: string): string {
  const fecha = new Date(iso);
  const dos = (n: number) => String(n).padStart(2, "0");
  return (
    `${dos(fecha.getDate())}-${dos(fecha.getMonth() + 1)}-${fecha.getFullYear()} ` +
    `${dos(fecha.getHours())}:${dos(fecha.getMinutes())}`
  );
}
