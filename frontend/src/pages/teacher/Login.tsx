/**
 * Acceso docente. Porta `teacher/login.html`.
 *
 * El panel de curación decide **qué material llega a las microcápsulas**, así
 * que está separado de las vistas del estudiante. Cuando `configurado` es
 * `false` significa que `TEACHER_PASSWORD` se dejó vacía a propósito: el panel
 * está cerrado para todos y hay que decirlo con el nombre exacto de la variable,
 * no con «clave incorrecta», que mandaría a buscar el problema donde no está.
 */

import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { Alerta } from "../../components/Alerta";
import { useSesionDocente } from "../../contexts/SesionDocente";

export function Login() {
  const { autenticado, configurado, cargando, entrar } = useSesionDocente();
  const navegar = useNavigate();
  const ubicacion = useLocation();

  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  // A dónde iba el docente antes de que lo mandaran acá. Solo rutas internas
  // del panel: si viniera de fuera sería un redirector abierto.
  const destino =
    (ubicacion.state as { destino?: string } | null)?.destino ?? "/docente/curacion";

  if (cargando) return null;
  // Con la sesión abierta el login ya no tiene nada que preguntar.
  if (autenticado) return <Navigate to={destino} replace />;

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(undefined);
    setEnviando(true);
    try {
      await entrar(usuario, clave);
      navegar(destino, { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="card card-login">
      <h1 className="text-lg mb-2">Acceso docente</h1>
      <p className="text-muted text-sm mb-4">
        El panel de curación decide <strong>qué material llega a las
        microcápsulas</strong>, así que está separado de las vistas del
        estudiante. Si vienes a estudiar, vuelve a <Link to="/catalogo">Temas</Link>.
      </p>

      {!configurado ? (
        <Alerta estado="error">
          <strong>El panel está cerrado en esta instalación.</strong>{" "}
          <code>TEACHER_PASSWORD</code> quedó vacía en el archivo <code>.env</code>.
          Fíjala y reinicia el servidor:{" "}
          <code>TEACHER_PASSWORD=la-clave-que-elijas</code>
        </Alerta>
      ) : (
        <>
          {error && (
            <div className="mb-4">
              <Alerta estado="error">{error}</Alerta>
            </div>
          )}
          <form onSubmit={(e) => void enviar(e)}>
            <div className="form-group">
              <label className="form-label" htmlFor="usuario">
                Usuario
              </label>
              <input
                type="text"
                id="usuario"
                className="form-control"
                required
                autoFocus
                autoComplete="username"
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="clave">
                Clave
              </label>
              <input
                type="password"
                id="clave"
                className="form-control"
                required
                autoComplete="current-password"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={enviando}
            >
              {enviando ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}

/**
 * Envuelve las rutas del panel. Sin sesión manda al login recordando el destino.
 *
 * Es el equivalente en el cliente de `auth.requiere_docente`, pero **no lo
 * reemplaza**: la protección real la hace el servidor en cada petición. Esto
 * solo evita mostrar una pantalla que se va a llenar de errores 401.
 */
export function RutaDocente({ children }: { children: React.ReactNode }) {
  const { autenticado, cargando } = useSesionDocente();
  const ubicacion = useLocation();

  if (cargando) return null;
  if (!autenticado) {
    return (
      <Navigate to="/docente/login" state={{ destino: ubicacion.pathname }} replace />
    );
  }
  return <>{children}</>;
}
