/**
 * Rutas de la aplicación.
 *
 * Las del estudiante son públicas (el sistema no autentica estudiantes: el
 * cap. 9 los identifica por su diagnóstico, no por una credencial). Las del
 * docente van envueltas en `RutaDocente`, que es el equivalente en el cliente
 * del guardián del servidor — **no lo reemplaza**: la protección real la hace
 * `auth.requiere_docente_api` en cada petición, y esto solo evita mostrar una
 * pantalla que se va a llenar de 401.
 */

import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ProveedorSesionDocente } from "./contexts/SesionDocente";
import { Catalogo } from "./pages/student/Catalogo";
import { Perfil } from "./pages/student/Perfil";
import { Vark } from "./pages/student/Vark";
import { Visor } from "./pages/student/Visor";
import { Analiticas } from "./pages/teacher/Analiticas";
import { Curacion } from "./pages/teacher/Curacion";
import { Login, RutaDocente } from "./pages/teacher/Login";
import { Simulador } from "./pages/teacher/Simulador";

export function App() {
  return (
    <ProveedorSesionDocente>
      <Layout>
        <Routes>
          {/* Igual que el `/` de FastAPI, que redirige al cuestionario. */}
          <Route path="/" element={<Navigate to="/vark" replace />} />

          <Route path="/vark" element={<Vark />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/catalogo" element={<Catalogo />} />
          <Route path="/visor/:idObjetivo" element={<Visor />} />

          <Route path="/docente/login" element={<Login />} />
          <Route
            path="/docente/curacion"
            element={
              <RutaDocente>
                <Curacion />
              </RutaDocente>
            }
          />
          <Route
            path="/docente/analiticas"
            element={
              <RutaDocente>
                <Analiticas />
              </RutaDocente>
            }
          />
          <Route
            path="/docente/simulador"
            element={
              <RutaDocente>
                <Simulador />
              </RutaDocente>
            }
          />

          <Route path="*" element={<Navigate to="/vark" replace />} />
        </Routes>
      </Layout>
    </ProveedorSesionDocente>
  );
}
