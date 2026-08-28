/**
 * Panel de curación. Porta `teacher/curation.html`, `_bandeja.html` y `_fila.html`.
 *
 * Es la única puerta por la que el material institucional entra al sistema, así
 * que esta pantalla no es administrativa: es la barrera del cap. 12/13. Ningún
 * fragmento sin validar llega jamás al prompt.
 *
 * **La decisión de diseño que se ve en pantalla:** el botón de validar no existe
 * por sí solo, va junto al selector de objetivo. Validar un fragmento sin
 * objetivo lo dejaría inalcanzable para siempre —el retriever recupera por
 * `id_objetivo`—, aprobado, sin error visible y sin llegar nunca a una cápsula.
 * El servidor lo bloquea (`curation.validar`); acá se hace además evidente.
 */

import { useState } from "react";

import { api } from "../../api/client";
import type {
  Documento,
  FragmentoEnCuracion,
  Objetivo,
  ResultadoIngesta,
} from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { useApi } from "../../hooks/useApi";

/** Cuántos fragmentos muestra la bandeja: el mismo tope que la vista Jinja. */
const LIMITE_BANDEJA = 60;

interface Aviso {
  estado: "ok" | "error";
  texto: string;
}

export function Curacion() {
  const [idDocumento, setIdDocumento] = useState<number | null>(null);

  const objetivos = useApi<Objetivo[]>("/api/objetivos");
  const documentos = useApi<Documento[]>("/api/documentos");
  const bandeja = useApi<FragmentoEnCuracion[]>(
    `/api/fragmentos?estado=pendiente&limite=${LIMITE_BANDEJA}` +
      (idDocumento ? `&id_documento=${idDocumento}` : ""),
  );

  const [aviso, setAviso] = useState<Aviso>();

  function refrescarTodo() {
    bandeja.recargar();
    documentos.recargar();
    objetivos.recargar();
  }

  return (
    <>
      <div className="mb-8">
        <h1 className="mb-2">Base de Conocimiento: Curación de Contenido</h1>
        <p className="text-muted">
          Sube el documento oficial y valida los fragmentos que lo respaldan.{" "}
          <strong>Ningún fragmento sin validar llega a una microcápsula</strong>:
          es lo que garantiza que el contenido generado esté anclado a material
          institucional.
        </p>
      </div>

      <FormularioObjetivo
        objetivos={objetivos.datos ?? []}
        alCrear={() => {
          objetivos.recargar();
          bandeja.recargar();
        }}
      />

      <FormularioDocumento alSubir={refrescarTodo} />

      {(documentos.datos ?? []).length > 0 && (
        <TablaDocumentos
          documentos={documentos.datos ?? []}
          idFiltrado={idDocumento}
          alFiltrar={setIdDocumento}
        />
      )}

      {(objetivos.datos ?? []).length === 0 && !objetivos.cargando && (
        <div className="mb-8">
          <Alerta estado="error">
            <strong>No hay objetivos de aprendizaje cargados.</strong> Sin ellos no
            se puede validar ningún fragmento, porque el retriever recupera por
            objetivo y un fragmento validado sin objetivo queda inalcanzable para
            siempre. Crea el primero en el formulario de arriba.
          </Alerta>
        </div>
      )}

      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg">Bandeja de revisión</h2>
          <div className="flex items-center gap-4">
            {(objetivos.datos ?? []).length > 0 && (
              <BotonEtiquetar
                idDocumento={idDocumento}
                alTerminar={(nuevoAviso) => {
                  setAviso(nuevoAviso);
                  bandeja.recargar();
                }}
              />
            )}
            {idDocumento !== null && (
              <button
                type="button"
                className="btn btn-outline text-sm"
                style={{ padding: "0.25rem 0.75rem" }}
                onClick={() => setIdDocumento(null)}
              >
                Ver todos los documentos
              </button>
            )}
          </div>
        </div>

        {aviso && (
          <div className="mb-4">
            <Alerta estado={aviso.estado}>{aviso.texto}</Alerta>
          </div>
        )}

        {bandeja.cargando ? (
          <Cargando />
        ) : bandeja.error ? (
          <Alerta estado="error">{bandeja.error.message}</Alerta>
        ) : (
          <Bandeja
            fragmentos={bandeja.datos ?? []}
            objetivos={objetivos.datos ?? []}
            alRevisar={() => bandeja.recargar()}
          />
        )}
      </div>
    </>
  );
}

// --- Alta de objetivos --------------------------------------------------------

function FormularioObjetivo({
  objetivos,
  alCrear,
}: {
  objetivos: Objetivo[];
  alCrear: () => void;
}) {
  const [campos, setCampos] = useState({
    codigo_objetivo: "",
    asignatura: "",
    unidad: "",
    tema: "",
    nivel_taxonomico: "",
    descripcion: "",
  });
  const [aviso, setAviso] = useState<Aviso>();
  const [enviando, setEnviando] = useState(false);

  function actualizar(campo: keyof typeof campos, valor: string) {
    setCampos((previo) => ({ ...previo, [campo]: valor }));
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      const creado = await api.post<Objetivo>("/api/objetivos", {
        codigo_objetivo: campos.codigo_objetivo.trim(),
        asignatura: campos.asignatura.trim(),
        unidad: campos.unidad.trim(),
        tema: campos.tema.trim(),
        descripcion: campos.descripcion.trim() || null,
        nivel_taxonomico: campos.nivel_taxonomico.trim() || null,
      });
      setAviso({
        estado: "ok",
        texto:
          `Objetivo «${creado.codigo_objetivo} — ${creado.tema}» creado. ` +
          `Ya puedes asignarle fragmentos en la bandeja de revisión.`,
      });
      setCampos({
        codigo_objetivo: "",
        asignatura: "",
        unidad: "",
        tema: "",
        nivel_taxonomico: "",
        descripcion: "",
      });
      alCrear();
    } catch (e) {
      setAviso({ estado: "error", texto: (e as Error).message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="card mb-8">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg">Objetivos de aprendizaje</h2>
        <span className="text-sm text-muted">{objetivos.length} en el catálogo</span>
      </div>
      <p className="text-muted text-sm mb-4">
        Son los temas a los que se asigna cada fragmento.{" "}
        <strong>Sin al menos uno no se puede validar nada</strong>, porque el
        retriever recupera por objetivo. Para cargar un plan de estudios completo
        de una vez está <code>python scripts/cargar_objetivos.py data/objetivos.csv</code>.
      </p>

      <form
        onSubmit={(e) => void enviar(e)}
        className="flex items-center gap-4"
        style={{ flexWrap: "wrap" }}
      >
        <input
          type="text"
          className="form-control"
          maxLength={30}
          required
          placeholder="Código (ej. UX-U1-01)"
          style={{ maxWidth: "190px" }}
          value={campos.codigo_objetivo}
          onChange={(e) => actualizar("codigo_objetivo", e.target.value)}
        />
        <input
          type="text"
          className="form-control"
          maxLength={100}
          required
          placeholder="Asignatura"
          style={{ maxWidth: "200px" }}
          value={campos.asignatura}
          onChange={(e) => actualizar("asignatura", e.target.value)}
        />
        <input
          type="text"
          className="form-control"
          maxLength={100}
          required
          placeholder="Unidad"
          style={{ maxWidth: "200px" }}
          value={campos.unidad}
          onChange={(e) => actualizar("unidad", e.target.value)}
        />
        <input
          type="text"
          className="form-control"
          maxLength={150}
          required
          placeholder="Tema"
          style={{ maxWidth: "220px" }}
          value={campos.tema}
          onChange={(e) => actualizar("tema", e.target.value)}
        />
        <input
          type="text"
          className="form-control"
          maxLength={50}
          placeholder="Nivel (opcional)"
          style={{ maxWidth: "160px" }}
          value={campos.nivel_taxonomico}
          onChange={(e) => actualizar("nivel_taxonomico", e.target.value)}
        />
        <input
          type="text"
          className="form-control"
          placeholder="Descripción (opcional)"
          style={{ maxWidth: "320px" }}
          value={campos.descripcion}
          onChange={(e) => actualizar("descripcion", e.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={enviando}>
          {enviando ? "Creando…" : "Crear objetivo"}
        </button>
      </form>

      {aviso && (
        <div className="mt-4">
          <Alerta estado={aviso.estado}>{aviso.texto}</Alerta>
        </div>
      )}

      {objetivos.length > 0 && (
        <details className="mt-4">
          <summary className="text-sm text-muted" style={{ cursor: "pointer" }}>
            Ver los {objetivos.length} objetivos cargados
          </summary>
          <ul className="mt-2 text-sm">
            {objetivos.map((objetivo) => (
              <li key={objetivo.id_objetivo}>
                <strong>{objetivo.codigo_objetivo}</strong> — {objetivo.asignatura} ·{" "}
                {objetivo.unidad} · {objetivo.tema}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// --- Ingesta ------------------------------------------------------------------

function FormularioDocumento({ alSubir }: { alSubir: () => void }) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [asignatura, setAsignatura] = useState("");
  const [aviso, setAviso] = useState<Aviso>();
  const [subiendo, setSubiendo] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!archivo) return;

    const datos = new FormData();
    datos.append("archivo", archivo);
    setSubiendo(true);
    try {
      const ruta =
        "/api/documentos" +
        (asignatura.trim() ? `?asignatura=${encodeURIComponent(asignatura.trim())}` : "");
      const resultado = await api.subir<ResultadoIngesta>(ruta, datos);
      setAviso({
        estado: "ok",
        texto:
          `«${resultado.titulo}» quedó ingerido: ${resultado.total_fragmentos} ` +
          `fragmentos sobre ${resultado.pagina_maxima} página(s), ` +
          `${resultado.palabras_totales} palabras. Todos están pendientes de ` +
          `revisión: ninguno llegará a una cápsula hasta que lo valides.`,
      });
      setArchivo(null);
      alSubir();
    } catch (e) {
      setAviso({ estado: "error", texto: (e as Error).message });
    } finally {
      setSubiendo(false);
    }
  }

  return (
    <div className="card mb-8">
      <h2 className="text-lg mb-4">Cargar nuevo documento</h2>
      <form
        onSubmit={(e) => void enviar(e)}
        className="flex items-center gap-4"
        style={{ flexWrap: "wrap" }}
      >
        <input
          type="file"
          accept=".pdf,.pptx"
          className="form-control"
          required
          style={{ maxWidth: "340px" }}
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
        />
        <input
          type="text"
          className="form-control"
          maxLength={100}
          placeholder="Asignatura (opcional)"
          style={{ maxWidth: "240px" }}
          value={asignatura}
          onChange={(e) => setAsignatura(e.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={subiendo}>
          {subiendo ? "Ingiriendo…" : "Subir e ingerir"}
        </button>
      </form>
      {aviso && (
        <div className="mt-4">
          <Alerta estado={aviso.estado}>{aviso.texto}</Alerta>
        </div>
      )}
    </div>
  );
}

function TablaDocumentos({
  documentos,
  idFiltrado,
  alFiltrar,
}: {
  documentos: Documento[];
  idFiltrado: number | null;
  alFiltrar: (id: number | null) => void;
}) {
  return (
    <div className="card mb-8">
      <h2 className="text-lg mb-4">Documentos cargados</h2>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Documento</th>
              <th>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {documentos.map((documento) => (
              <tr key={documento.id_documento}>
                <td>
                  <div className="font-medium">{documento.titulo}</div>
                  <div className="text-sm text-muted">
                    {documento.formato}
                    {documento.asignatura ? ` · ${documento.asignatura}` : ""}
                  </div>
                </td>
                <td>
                  {documento.estado_curacion === "validado" ? (
                    <span className="badge badge-success">validado</span>
                  ) : documento.estado_curacion === "rechazado" ? (
                    <span className="badge badge-danger">rechazado</span>
                  ) : (
                    <span className="badge badge-warning">pendiente</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-outline text-sm"
                    style={{ padding: "0.25rem 0.75rem" }}
                    onClick={() =>
                      alFiltrar(
                        idFiltrado === documento.id_documento
                          ? null
                          : documento.id_documento,
                      )
                    }
                  >
                    {idFiltrado === documento.id_documento
                      ? "Quitar filtro"
                      : "Revisar solo este"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- Etiquetado por IA --------------------------------------------------------

function BotonEtiquetar({
  idDocumento,
  alTerminar,
}: {
  idDocumento: number | null;
  alTerminar: (aviso: Aviso) => void;
}) {
  const [enProceso, setEnProceso] = useState(false);

  async function etiquetar() {
    setEnProceso(true);
    try {
      const resumen = await api.post<{
        total: number;
        con_objetivo: number;
        sin_objetivo: number;
        fallidos: number;
        primer_error: string | null;
      }>(
        "/api/fragmentos/etiquetar" +
          (idDocumento ? `?id_documento=${idDocumento}` : ""),
      );

      if (resumen.total === 0) {
        alTerminar({
          estado: "ok",
          texto:
            "No hay fragmentos pendientes sin objetivo para sugerir" +
            (idDocumento ? " en este documento." : "."),
        });
        return;
      }

      const partes = [
        `${resumen.con_objetivo} de ${resumen.total} fragmentos con objetivo sugerido`,
      ];
      if (resumen.sin_objetivo > 0) {
        partes.push(`${resumen.sin_objetivo} sin un objetivo claro (revísalos a mano)`);
      }
      if (resumen.fallidos > 0) {
        partes.push(`${resumen.fallidos} fallaron: ${resumen.primer_error}`);
      }
      alTerminar({
        estado: resumen.con_objetivo > 0 ? "ok" : "error",
        texto:
          partes.join("; ") +
          ". Revisa la bandeja: los campos ya vienen prellenados, pero cada " +
          "fragmento se sigue validando a mano.",
      });
    } catch (e) {
      alTerminar({ estado: "error", texto: (e as Error).message });
    } finally {
      setEnProceso(false);
    }
  }

  return (
    <button
      type="button"
      className="btn btn-outline text-sm"
      style={{ padding: "0.25rem 0.75rem" }}
      title="El modelo propone objetivo y etiqueta para lo que sigue sin clasificar; tú sigues validando cada fragmento."
      disabled={enProceso}
      onClick={() => void etiquetar()}
    >
      {enProceso ? "Consultando al modelo…" : "Sugerir objetivos con IA"}
    </button>
  );
}

// --- Bandeja ------------------------------------------------------------------

function Bandeja({
  fragmentos,
  objetivos,
  alRevisar,
}: {
  fragmentos: FragmentoEnCuracion[];
  objetivos: Objetivo[];
  alRevisar: () => void;
}) {
  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Origen</th>
            <th>Fragmento</th>
            <th>Objetivo de aprendizaje</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {fragmentos.length === 0 ? (
            <tr>
              <td colSpan={4} className="text-center text-muted py-8">
                No hay fragmentos pendientes de revisión.
              </td>
            </tr>
          ) : (
            fragmentos.map((fragmento) => (
              <FilaFragmento
                key={fragmento.id_fragmento}
                fragmento={fragmento}
                objetivos={objetivos}
                alRevisar={alRevisar}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function FilaFragmento({
  fragmento,
  objetivos,
  alRevisar,
}: {
  fragmento: FragmentoEnCuracion;
  objetivos: Objetivo[];
  alRevisar: () => void;
}) {
  // El selector arranca con la propuesta del modelo si la hay. Sigue siendo solo
  // una propuesta: el POST de «Validar» es lo único que la vuelve real. El
  // servidor nunca escribió `id_objetivo` con ella (`knowledge/tagger.py`
  // guarda en `metadatos_json`), así que si el modelo se equivocó no hay nada
  // que deshacer: basta con elegir otra opción antes de validar.
  const [idObjetivo, setIdObjetivo] = useState<string>(
    String(fragmento.id_objetivo ?? fragmento.sugerido_id_objetivo ?? ""),
  );
  const [error, setError] = useState<string>();
  const [enProceso, setEnProceso] = useState(false);

  async function ejecutar(accion: "validar" | "descartar") {
    setError(undefined);
    setEnProceso(true);
    try {
      if (accion === "validar") {
        await api.post(`/api/fragmentos/${fragmento.id_fragmento}/validar`, {
          id_objetivo: idObjetivo ? Number(idObjetivo) : null,
        });
      } else {
        await api.post(`/api/fragmentos/${fragmento.id_fragmento}/descartar`);
      }
      alRevisar();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEnProceso(false);
    }
  }

  const paginas =
    fragmento.pagina_inicio !== null
      ? `Pág. ${fragmento.pagina_inicio}` +
        (fragmento.pagina_fin && fragmento.pagina_fin !== fragmento.pagina_inicio
          ? `–${fragmento.pagina_fin}`
          : "") +
        " · "
      : "";

  return (
    <tr>
      <td>
        <div className="font-medium">{fragmento.documento_titulo}</div>
        <div className="text-sm text-muted">
          {paginas}
          {fragmento.tipo_fragmento} · {fragmento.palabras} palabras
        </div>
      </td>
      <td>
        <div className="text-sm texto-fragmento">{fragmento.contenido_texto}</div>
        {error && (
          <div className="mt-2 text-sm">
            <Alerta estado="error">{error}</Alerta>
          </div>
        )}
      </td>
      <td>
        {fragmento.estado_validacion === "validado" ? (
          <span className="badge badge-success">validado</span>
        ) : fragmento.estado_validacion === "descartado" ? (
          <span className="badge badge-danger">descartado</span>
        ) : (
          <>
            <select
              className="form-control text-sm"
              style={{ minWidth: "220px" }}
              value={idObjetivo}
              onChange={(e) => setIdObjetivo(e.target.value)}
            >
              <option value="">— sin asignar —</option>
              {objetivos.map((objetivo) => (
                <option key={objetivo.id_objetivo} value={objetivo.id_objetivo}>
                  {objetivo.codigo_objetivo} · {objetivo.tema}
                </option>
              ))}
            </select>
            {(fragmento.sugerido_etiqueta || fragmento.sugerido_motivo) && (
              <div className="text-sm text-muted mt-1">
                <span className="badge badge-primary">IA</span>{" "}
                {fragmento.sugerido_etiqueta}
                {fragmento.sugerido_motivo ? ` — ${fragmento.sugerido_motivo}` : ""}
              </div>
            )}
          </>
        )}
      </td>
      <td>
        {fragmento.estado_validacion === "pendiente" ? (
          <div className="flex gap-2">
            <button
              type="button"
              className="btn btn-outline text-sm"
              style={{
                padding: "0.25rem 0.75rem",
                borderColor: "var(--success)",
                color: "var(--success)",
              }}
              disabled={enProceso}
              onClick={() => void ejecutar("validar")}
            >
              Validar
            </button>
            <button
              type="button"
              className="btn btn-outline text-sm"
              style={{
                padding: "0.25rem 0.75rem",
                borderColor: "var(--danger)",
                color: "var(--danger)",
              }}
              disabled={enProceso}
              onClick={() => void ejecutar("descartar")}
            >
              Descartar
            </button>
          </div>
        ) : (
          <span className="text-sm text-muted">Revisado</span>
        )}
      </td>
    </tr>
  );
}
