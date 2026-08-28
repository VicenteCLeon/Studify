/**
 * Cabecera y contenedor compartidos. Porta `base.html`.
 *
 * La barra tiene dos formas y la diferencia no es cosmética: los enlaces del
 * panel **solo existen para quien tiene sesión de docente**. Mostrarlos a un
 * estudiante sería ofrecerle una puerta que no es suya y que el servidor va a
 * cerrarle igual (`auth.requiere_docente`).
 */

import { NavLink, useNavigate } from "react-router-dom";

import { useSesionDocente } from "../contexts/SesionDocente";

export function Layout({ children }: { children: React.ReactNode }) {
  const { autenticado, salir } = useSesionDocente();
  const navegar = useNavigate();

  async function cerrarSesion() {
    await salir();
    navegar("/catalogo");
  }

  return (
    <>
      <header className="app-header">
        <div className="container">
          <div className="brand">
            <NavLink to="/">RepasAi</NavLink>
          </div>
          <nav className="nav-links">
            <NavLink to="/catalogo">Temas</NavLink>
            <NavLink to="/perfil">Mi perfil</NavLink>
            {autenticado ? (
              <>
                <NavLink to="/docente/curacion">Curación</NavLink>
                <NavLink to="/docente/analiticas">Analíticas</NavLink>
                <NavLink to="/docente/simulador">Simulador</NavLink>
                <button
                  type="button"
                  onClick={() => void cerrarSesion()}
                  className="btn btn-outline btn-nav"
                >
                  Salir
                </button>
              </>
            ) : (
              <NavLink to="/docente/login" className="btn btn-outline btn-nav">
                Soy docente
              </NavLink>
            )}
          </nav>
        </div>
      </header>

      <main className="main-content">
        <div className="container">{children}</div>
      </main>
    </>
  );
}
