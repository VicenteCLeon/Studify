/**
 * Perfil del estudiante. Porta `student/profile.html`.
 *
 * Muestra las dos mitades del cap. 11: el vector porcentual persistido y la
 * **configuración de contenido** que las reglas derivaron de él. La segunda es
 * la que condiciona la cápsula, así que se muestra explícita: es lo que permite
 * comprobar en la demo que la adaptación existe antes siquiera de generar nada.
 *
 * Sin sesión el servidor responde 401 y acá se manda al cuestionario, que es lo
 * mismo que hacía `_sin_sesion()` con un 303.
 */

import { Navigate, useNavigate } from "react-router-dom";

import { esNoAutenticado } from "../../api/client";
import type { PerfilLegible } from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { BarrasVark } from "../../components/BarrasVark";
import { useApi } from "../../hooks/useApi";

export function Perfil() {
  const { datos, cargando, error } = useApi<PerfilLegible>("/api/perfil");
  const navegar = useNavigate();

  if (cargando) return <Cargando texto="Cargando tu perfil…" />;
  // Sin diagnóstico no hay nada que mostrar: se manda a responderlo.
  if (error && esNoAutenticado(error)) return <Navigate to="/vark" replace />;
  if (error) return <Alerta estado="error">{error.message}</Alerta>;
  if (!datos) return <Navigate to="/vark" replace />;

  const { configuracion } = datos;

  return (
    <div className="card" style={{ maxWidth: "860px", margin: "0 auto" }}>
      <div className="text-center mb-6">
        <h1 className="mb-2">
          Tu Perfil: <span className="text-primary">{datos.canal_principal}</span>
        </h1>
        <p className="text-muted">Así es como procesas mejor la información.</p>
        <div className="flex justify-center gap-2 mt-4">
          <span className="badge badge-primary">{datos.modalidad}</span>
          <span className="badge badge-success">
            Jerarquía {datos.canal_primario}→{datos.canal_secundario}
          </span>
          <span className="badge badge-warning">
            Diagnóstico #{datos.id_diagnostico}
          </span>
        </div>
      </div>

      <div className="mb-8">
        <BarrasVark canales={datos.canales} />
      </div>

      <div className="capsule-activity mb-8">
        <h3 className="mb-2">¿Qué significa esto para ti?</h3>
        <p>{datos.explicacion}</p>
      </div>

      <h3 className="mb-2">Cómo se construirán tus microcápsulas</h3>
      <p className="text-muted text-sm mb-4">
        Estos parámetros los derivó el sistema desde tu vector y son los que
        recibe el generador. No son una descripción de tu personalidad: son
        instrucciones de armado.
      </p>

      <div className="grid-config mb-6">
        <div className="dato">
          <span className="dato-valor">{configuracion.palabras_texto}</span>
          <span className="dato-etiqueta">palabras de contenido</span>
        </div>
        <div className="dato">
          <span className="dato-valor">{configuracion.recursos_visuales}</span>
          <span className="dato-etiqueta">recursos visuales</span>
        </div>
        <div className="dato">
          <span className="dato-valor">{configuracion.componentes_practicos}</span>
          <span className="dato-etiqueta">componentes prácticos</span>
        </div>
        <div className="dato">
          <span className="dato-valor dato-texto">{configuracion.tono}</span>
          <span className="dato-etiqueta">registro de redacción</span>
        </div>
      </div>

      <ul className="lista-directivas mb-8">
        {datos.directivas.map((directiva, i) => (
          <li key={i}>{directiva}</li>
        ))}
      </ul>

      <div className="flex justify-center gap-4">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navegar("/catalogo")}
        >
          Ir al Catálogo de Temas
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => navegar("/vark")}
        >
          Volver a responder
        </button>
      </div>
    </div>
  );
}
