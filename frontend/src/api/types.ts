/**
 * Tipos del contrato con la API.
 *
 * Son el espejo en TypeScript de los esquemas Pydantic de `src/studify/api/`.
 * Se escriben a mano y no se generan desde el OpenAPI a propósito: un generador
 * agregaría un paso de build y una dependencia más a un proyecto que no los
 * necesita, y estos contratos cambian poco. La contrapartida es que hay que
 * mantenerlos sincronizados; por eso cada bloque dice de qué esquema viene.
 */

// --- generation/schemas.py ----------------------------------------------------

/** Los siete tipos de bloque del contrato de la microcápsula. */
export type TipoBloque =
  | "parrafo"
  | "lista_pasos"
  | "tabla"
  | "esquema"
  | "analogia"
  | "ejemplo_resuelto"
  | "glosario";

/** `cuerpo` admite tres formas: texto, lista de ítems, o matriz de filas. */
export type CuerpoBloque = string | string[] | string[][];

export interface BloqueContenido {
  tipo: TipoBloque;
  encabezado: string | null;
  cuerpo: CuerpoBloque;
}

export interface Fuente {
  id_fragmento: number;
  documento: string;
  pagina: number | null;
}

export interface Actividad {
  tipo: "quiz_mc" | "intentalo_tu";
  pregunta: string;
  alternativas: string[];
  /** Solo llega en el simulador del docente; nunca en el flujo del estudiante. */
  indice_correcta?: number | null;
  retroalimentacion?: string;
}

// --- api/schemas_capsulas.py --------------------------------------------------

export type OrigenCapsula = "generada" | "cache" | "cache_compartido";

/** El tema al que pertenece la cápsula, para las insignias del visor. */
export interface ObjetivoDeCapsula {
  id_objetivo: number;
  codigo_objetivo: string;
  asignatura: string;
  unidad: string;
  tema: string;
}

export interface Capsula {
  id_capsula: number;
  id_estudiante: number;
  id_objetivo: number;
  objetivo: ObjetivoDeCapsula | null;
  fecha_generacion: string;
  estado_validacion: string;
  titulo: string;
  objetivo_aprendizaje: string;
  activacion: string;
  concepto_central: string;
  representacion_adaptativa: BloqueContenido[];
  ejemplo: BloqueContenido;
  /**
   * Sin `indice_correcta` ni `retroalimentacion`: el servidor los omite a
   * propósito para que la respuesta correcta no esté en la red antes de que el
   * estudiante conteste.
   */
  actividad: Actividad;
  fuentes: Fuente[];
  origen: OrigenCapsula;
  modelo_llm: string | null;
  intentos: number | null;
  segundos: number | null;
}

// --- api/schemas_ui.py --------------------------------------------------------

export interface AlternativaItem {
  /** `a` | `b` | `c` | `d`. El canal VARK no viaja al cliente (cap. 17.1). */
  letra: string;
  texto: string;
}

export interface ItemInstrumento {
  numero: number;
  enunciado: string;
  alternativas: AlternativaItem[];
}

export interface SesionEstudiante {
  id_estudiante: number | null;
  tiene_diagnostico: boolean;
}

export interface BarraCanal {
  canal: string;
  nombre: string;
  color: string;
  ancho: string;
  texto: string;
}

export interface PerfilLegible {
  id_diagnostico: number;
  canales: BarraCanal[];
  canal_principal: string;
  canal_primario: string;
  canal_secundario: string;
  modalidad: string;
  explicacion: string;
  configuracion: {
    recursos_visuales: number;
    palabras_texto: number;
    componentes_practicos: number;
    tono: string;
    pesos: {
      texto: number;
      visual: number;
      narrativo: number;
      practico: number;
    };
  };
  directivas: string[];
}

export interface ResultadoActividad {
  estado: "ok" | "error" | "esperada";
  titulo: string;
  retroalimentacion: string;
  /** Solo llega cuando el estudiante ya falló. */
  correcta: string | null;
  numero_intento: number | null;
}

// --- api/schemas_knowledge.py -------------------------------------------------

export interface TemaDisponible {
  id_objetivo: number;
  codigo_objetivo: string;
  tema: string;
  descripcion: string | null;
  fragmentos_disponibles: number;
}

export interface UnidadDisponible {
  unidad: string;
  temas: TemaDisponible[];
}

export interface AsignaturaDisponible {
  asignatura: string;
  unidades: UnidadDisponible[];
}

export interface Objetivo {
  id_objetivo: number;
  codigo_objetivo: string;
  asignatura: string;
  unidad: string;
  tema: string;
  descripcion: string | null;
  nivel_taxonomico: string | null;
  estado: string;
}

export interface Documento {
  id_documento: number;
  titulo: string;
  tipo_documento: string | null;
  formato: string;
  origen: string | null;
  asignatura: string | null;
  version: string | null;
  estado_curacion: string;
  fecha_carga: string;
}

export interface FragmentoEnCuracion {
  id_fragmento: number;
  id_documento: number;
  id_objetivo: number | null;
  numero_fragmento: number;
  tipo_fragmento: string;
  contenido_texto: string | null;
  pagina_inicio: number | null;
  pagina_fin: number | null;
  etiqueta_tematica: string | null;
  estado_validacion: string;
  documento_titulo: string;
  objetivo_codigo: string | null;
  palabras: number;
  /** Propuesta del tagger. Solo viaja mientras el fragmento no tiene objetivo. */
  sugerido_id_objetivo: number | null;
  sugerido_etiqueta: string | null;
  sugerido_motivo: string | null;
}

export interface ResumenCuracion {
  id_documento: number;
  pendiente: number;
  validado: number;
  descartado: number;
}

export interface ResultadoIngesta {
  id_documento: number;
  titulo: string;
  total_fragmentos: number;
  pagina_maxima: number;
  palabras_totales: number;
}

// --- api/schemas_panel.py -----------------------------------------------------

export type EstadoCobertura = "sin_material" | "escaso" | "cubierto";

export interface FilaCobertura {
  objetivo: {
    id_objetivo: number;
    codigo_objetivo: string;
    asignatura: string;
    unidad: string;
    tema: string;
  };
  total: number;
  tipos: { tipo: string; cantidad: number }[];
  canales: {
    canal: string;
    nombre: string;
    cantidad: number;
    /** Hay material, pero nada del tipo que este canal aprovecha. */
    degradado: boolean;
  }[];
  estado: EstadoCobertura;
}

export interface FilaRendimiento {
  tema: string;
  alumnos: number;
  primeras: number;
  aciertos: number;
  abiertas: number;
  reintentos: number;
  /** `null` (no `0`) cuando no hay quiz corregible: no es que todos fallaran. */
  porcentaje: number | null;
}

export interface CapsulaHistorial {
  id_capsula: number;
  id_estudiante: number;
  id_objetivo: number;
  titulo: string;
  estado_validacion: string;
  modelo_llm: string | null;
  fecha_generacion: string;
}

export interface Analiticas {
  cobertura: FilaCobertura[];
  sin_clasificar: number;
  rendimiento: FilaRendimiento[];
  vark_total: number;
  vark_barras: BarraCanal[];
  capsulas: CapsulaHistorial[];
}

/** La cápsula del simulador: sin `id_capsula` porque no se persiste. */
export interface CapsulaSimulada {
  titulo: string;
  objetivo_aprendizaje: string;
  activacion: string;
  concepto_central: string;
  representacion_adaptativa: BloqueContenido[];
  ejemplo: BloqueContenido;
  /** Acá sí viaja entera: el docente vino a revisar la calidad de la pregunta. */
  actividad: Actividad;
  fuentes: Fuente[];
}

export interface ColumnaSimulacion {
  canal: string;
  nombre_canal: string;
  color_canal: string;
  capsula: CapsulaSimulada | null;
  palabras: number | null;
  /** Cada canal falla por separado; si uno revienta los otros se siguen viendo. */
  error: string | null;
}

// --- web/routers/auth.py ------------------------------------------------------

export interface SesionDocente {
  autenticado: boolean;
  /** `false` si `TEACHER_PASSWORD` se dejó vacía: el panel está cerrado. */
  configurado: boolean;
}

// --- api/schemas.py -----------------------------------------------------------

export interface RespuestaItem {
  num_pregunta: number;
  alternativas: string[];
}

export interface DiagnosticoCreado {
  id_diagnostico: number;
  id_estudiante: number;
}
