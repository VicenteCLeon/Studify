/**
 * Catálogo de temas. Porta `student/catalog.html`.
 *
 * `GET /api/catalogo` viene con `solo_con_material=True` por defecto: **un
 * objetivo sin fragmentos validados no se muestra**. Es una regla de diseño de
 * la Fase 2 y no un detalle de presentación — ofrecer un tema sin material
 * curado llevaría al estudiante a un error de generación o, peor, a contenido
 * inventado (cap. 12/13).
 */

import { Link } from "react-router-dom";

import type { AsignaturaDisponible } from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { useApi } from "../../hooks/useApi";

export function Catalogo() {
  const { datos, cargando, error } =
    useApi<AsignaturaDisponible[]>("/api/catalogo");

  if (cargando) return <Cargando texto="Cargando el catálogo…" />;
  if (error) return <Alerta estado="error">{error.message}</Alerta>;

  const asignaturas = datos ?? [];

  return (
    <>
      <div className="mb-8">
        <h1 className="mb-2">Catálogo de Temas</h1>
        <p className="text-muted">
          Explora y selecciona lo que deseas estudiar hoy. Solo aparecen los temas
          que tienen material institucional ya revisado por un docente.
        </p>
      </div>

      <div className="card">
        {asignaturas.length === 0 ? (
          <div className="text-center py-8">
            <h3 className="mb-2">Todavía no hay temas disponibles</h3>
            <p className="text-muted mb-4">
              Un tema aparece acá cuando tiene material curado: el docente sube el
              documento oficial y valida los fragmentos que lo respaldan. Sin eso
              el sistema no puede generar una cápsula fundamentada, así que
              prefiere no ofrecer el tema antes que inventar el contenido.
            </p>
            <Link to="/docente/curacion" className="btn btn-outline">
              Ir al panel de curación
            </Link>
          </div>
        ) : (
          asignaturas.map((asignatura, indiceAsignatura) => (
            <details
              key={asignatura.asignatura}
              className="mb-4"
              open={indiceAsignatura === 0}
            >
              <summary className="text-lg">{asignatura.asignatura}</summary>
              <div>
                <ul className="unit-list">
                  {asignatura.unidades.map((unidad, indiceUnidad) => (
                    <li key={unidad.unidad}>
                      <details open={indiceUnidad === 0}>
                        <summary>{unidad.unidad}</summary>
                        <div>
                          <ul className="oa-list">
                            {unidad.temas.map((tema) => (
                              <li key={tema.id_objetivo} className="oa-card mb-2">
                                <span>
                                  <strong>{tema.codigo_objetivo}</strong> —{" "}
                                  {tema.tema}
                                  {tema.descripcion && (
                                    <>
                                      <br />
                                      <span className="text-sm text-muted">
                                        {tema.descripcion}
                                      </span>
                                    </>
                                  )}
                                  <br />
                                  <span className="text-sm text-muted">
                                    {tema.fragmentos_disponibles} fragmento
                                    {tema.fragmentos_disponibles === 1 ? "" : "s"} de
                                    material validado
                                  </span>
                                </span>
                                <Link
                                  to={`/visor/${tema.id_objetivo}`}
                                  className="btn btn-primary text-sm"
                                  style={{
                                    padding: "0.5rem 1rem",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  Estudiar
                                </Link>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </details>
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          ))
        )}
      </div>

      <div className="flex justify-center mt-8">
        <Link to="/perfil" className="text-muted">
          ← Ver mi perfil de aprendizaje
        </Link>
      </div>
    </>
  );
}
