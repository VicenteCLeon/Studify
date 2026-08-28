import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// El build sale a `src/studify/web/spa/` para que FastAPI lo sirva como estático
// desde el mismo origen que la API. Es una decisión de seguridad, no de comodidad:
// con el mismo origen la sesión sigue viajando en la cookie `httpOnly` firmada que
// ya existe (`web/sesion.py`), en vez de tener que pasar a un token en
// localStorage —que cualquier XSS podría leer— y sin necesidad de abrir CORS.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/studify/web/spa",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // En desarrollo el servidor de Vite reenvía a uvicorn todo lo que no es la
    // SPA. Así `npm run dev` da recarga en caliente sin que el navegador vea dos
    // orígenes distintos y sin tocar la configuración de cookies.
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/static": "http://127.0.0.1:8000",
    },
  },
});
