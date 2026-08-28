/**
 * Cuestionario VARK. Porta `student/vark.html` y la validación de `post_vark`.
 *
 * Dos reglas del instrumento (cap. 10) que la pantalla tiene que respetar y que
 * son fáciles de romper si uno asume que es un formulario normal:
 *
 * - se puede **marcar más de una** alternativa por ítem (de ahí las casillas y
 *   no un grupo de radios);
 * - se puede **dejar ítems en blanco**, así que no hay `required` por ítem. Lo
 *   único que se exige es al menos una selección en todo el cuestionario, que es
 *   la misma comprobación que hacía el handler de Jinja.
 *
 * Las alternativas viajan por **letra** (`a|b|c|d`), nunca por canal: el
 * servidor traduce la posición a V/A/R/K y así la matriz de puntuación no se
 * filtra al navegador (cap. 17.1).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../../api/client";
import type { DiagnosticoCreado, ItemInstrumento } from "../../api/types";
import { Alerta, Cargando } from "../../components/Alerta";
import { useApi } from "../../hooks/useApi";

const RANGOS = ["18 - 20 años", "21 - 23 años", "24 - 26 años", "27 años o más"];
const GENEROS = ["Femenino", "Masculino", "No Binario / otra identidad"];

export function Vark() {
  const { datos: items, cargando, error } = useApi<ItemInstrumento[]>("/api/instrumento");
  const navegar = useNavigate();

  // `Record<número de ítem, letras marcadas>`. Un ítem ausente es un ítem en
  // blanco, que el instrumento permite.
  const [marcadas, setMarcadas] = useState<Record<number, string[]>>({});
  const [rangoEtario, setRangoEtario] = useState("");
  const [genero, setGenero] = useState("");
  const [carrera, setCarrera] = useState("");
  const [aviso, setAviso] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  function alternar(numero: number, letra: string) {
    setMarcadas((previo) => {
      const actuales = previo[numero] ?? [];
      const nuevas = actuales.includes(letra)
        ? actuales.filter((l) => l !== letra)
        : [...actuales, letra];
      return { ...previo, [numero]: nuevas };
    });
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!items) return;

    const respuestas = items.map((item) => ({
      num_pregunta: item.numero,
      alternativas: marcadas[item.numero] ?? [],
    }));

    if (!respuestas.some((r) => r.alternativas.length > 0)) {
      setAviso(
        "No marcaste ninguna alternativa. Puedes dejar en blanco los ítems en " +
          "los que no te reconozcas, pero hace falta al menos una selección " +
          "para calcular tu perfil.",
      );
      return;
    }

    setAviso(undefined);
    setEnviando(true);
    try {
      const creado = await api.post<DiagnosticoCreado>("/api/diagnosticos", {
        estudiante: {
          rango_etario: rangoEtario || null,
          genero: genero || null,
          carrera: carrera.trim() || null,
        },
        respuestas,
      });
      // El diagnóstico ya existe; recién acá el navegador queda conectado. Son
      // dos pasos porque `POST /api/diagnosticos` es de la API pura y no sabe
      // de cookies.
      await api.post(`/api/sesion/${creado.id_estudiante}`);
      navegar("/perfil");
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  if (cargando) return <Cargando texto="Cargando el cuestionario…" />;
  if (error) return <Alerta estado="error">{error.message}</Alerta>;
  if (!items) return null;

  return (
    <div
      className="card"
      style={{ maxWidth: "860px", margin: "0 auto", backgroundColor: "#fafffc" }}
    >
      <div className="text-center mb-6">
        <h1 className="mb-2">Descubre tu Estilo de Aprendizaje</h1>
        <p className="text-muted">
          {items.length} situaciones cotidianas.{" "}
          <strong>Puedes marcar más de una alternativa</strong> en cada una, y{" "}
          <strong>dejar en blanco</strong> las que no te representen: ambas cosas
          son parte del instrumento y no afectan la validez de tu perfil.
        </p>
      </div>

      <form onSubmit={(e) => void enviar(e)}>
        <fieldset className="bloque-datos mb-8">
          <legend className="form-label">Antes de empezar (opcional)</legend>
          <p className="text-sm text-muted mb-4">
            Solo se usa para el análisis agregado de resultados. Nunca interviene
            en cómo se genera tu contenido.
          </p>
          <div className="grid-datos">
            <div className="form-group">
              <label className="form-label text-sm" htmlFor="rango_etario">
                Rango etario
              </label>
              <select
                className="form-control"
                id="rango_etario"
                value={rangoEtario}
                onChange={(e) => setRangoEtario(e.target.value)}
              >
                <option value="">Prefiero no decirlo</option>
                {RANGOS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label text-sm" htmlFor="genero">
                Género
              </label>
              <select
                className="form-control"
                id="genero"
                value={genero}
                onChange={(e) => setGenero(e.target.value)}
              >
                <option value="">Prefiero no decirlo</option>
                {GENEROS.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label text-sm" htmlFor="carrera">
                Carrera
              </label>
              <input
                className="form-control"
                type="text"
                id="carrera"
                maxLength={80}
                placeholder="Ej.: Ingeniería Civil Informática"
                value={carrera}
                onChange={(e) => setCarrera(e.target.value)}
              />
            </div>
          </div>
        </fieldset>

        {items.map((item) => (
          <div key={item.numero} className="form-group mb-8">
            <label className="form-label text-lg mb-4">
              <span className="numero-item">{item.numero}</span> {item.enunciado}
            </label>
            <div className="radio-group">
              {item.alternativas.map((alternativa) => (
                <label key={alternativa.letra} className="radio-option">
                  <input
                    type="checkbox"
                    checked={(marcadas[item.numero] ?? []).includes(alternativa.letra)}
                    onChange={() => alternar(item.numero, alternativa.letra)}
                  />
                  <span>{alternativa.texto}</span>
                </label>
              ))}
            </div>
          </div>
        ))}

        {aviso && (
          <div className="mb-4">
            <Alerta estado="error">{aviso}</Alerta>
          </div>
        )}

        <div className="flex justify-center mt-8">
          <button type="submit" className="btn btn-primary" disabled={enviando}>
            {enviando ? "Calculando tu perfil…" : "Descubrir mi Perfil"}
          </button>
        </div>
      </form>
    </div>
  );
}
