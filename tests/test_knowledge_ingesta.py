"""Tests de extracción y fragmentación (Fase 2).

Los tests de extracción **generan archivos PDF y PPTX de verdad** en `tmp_path`
y los vuelven a leer, en vez de simular la salida de las librerías. Un mock del
extractor solo comprobaría que el mock devuelve lo que se le dijo; lo que
interesa saber es si la detección de encabezados y el seguimiento de páginas
funcionan sobre archivos reales, que es donde fallan estas cosas.

Ninguno necesita Postgres: la extracción y el chunking son funciones puras.
"""

from pathlib import Path

import pytest

from studify.knowledge.chunker import (
    MAX_LARGO_ETIQUETA,
    FragmentoCrudo,
    fragmentar,
)
from studify.knowledge.extract import (
    BloqueTexto,
    FormatoNoSoportado,
    extraer,
    hash_archivo,
    normalizar,
)

# --- Normalización ------------------------------------------------------------


def test_normalizar_deshace_guion_de_corte():
    """Un término partido por el maquetado del PDF rompe el full-text search."""
    assert normalizar("proce-\nso de normaliza-\nción") == "proceso de normalización"


def test_normalizar_colapsa_saltos_y_espacios():
    assert normalizar("una   línea\n  y otra  ") == "una línea y otra"


def test_normalizar_compone_tildes():
    """Algunos PDF entregan 'o' + acento combinante en vez de 'ó'."""
    descompuesto = "normalización"
    assert normalizar(descompuesto) == "normalización"
    assert len(normalizar(descompuesto)) == len("normalización")


# --- Chunker: fronteras y tamaños --------------------------------------------


def _cuerpo(palabras: int, pagina: int = 1, palabra: str = "dato") -> BloqueTexto:
    return BloqueTexto(texto=" ".join([palabra] * palabras), pagina=pagina)


def test_titulo_abre_fragmento_nuevo_aunque_el_anterior_este_corto():
    """Frontera dura del cap. 12: dos secciones no comparten fragmento."""
    bloques = [
        BloqueTexto("Primera unidad", 1, es_titulo=True),
        _cuerpo(20, 1, "alfa"),
        BloqueTexto("Segunda unidad", 2, es_titulo=True),
        _cuerpo(20, 2, "beta"),
    ]
    frags = fragmentar(bloques)

    assert len(frags) == 2, "las dos secciones no deben fusionarse pese a ser cortas"
    assert frags[0].etiqueta_tematica == "Primera unidad"
    assert frags[1].etiqueta_tematica == "Segunda unidad"
    assert "beta" not in frags[0].texto
    assert "alfa" not in frags[1].texto


def test_ningun_fragmento_supera_el_maximo():
    bloques = [_cuerpo(90, pagina=i) for i in range(1, 21)]
    frags = fragmentar(bloques)

    assert frags, "debe emitir algo"
    for f in frags:
        assert f.palabras <= 350, f"fragmento {f.numero} con {f.palabras} palabras"


def test_bloque_descomunal_se_parte_sin_cortar_oraciones():
    """Un fragmento que empieza a media oración no se puede citar como fuente."""
    oracion = "El modelo relacional garantiza la trazabilidad de cada fragmento. "
    bloques = [BloqueTexto(oracion * 60, pagina=1)]

    frags = fragmentar(bloques)

    assert len(frags) > 1, "un bloque de ~600 palabras debe partirse"
    for f in frags:
        assert f.texto.rstrip().endswith("."), f"fragmento {f.numero} cortado a media oración"


def test_residuo_corto_se_fusiona_solo_dentro_del_mismo_tema():
    bloques = [
        BloqueTexto("Tema único", 1, es_titulo=True),
        _cuerpo(170, 1),
        _cuerpo(10, 2),  # residuo: por debajo del mínimo
    ]
    frags = fragmentar(bloques)

    assert len(frags) == 1, "el residuo del mismo tema debe absorberse"
    assert frags[0].pagina_inicio == 1
    assert frags[0].pagina_fin == 2, "el rango de páginas debe cubrir ambos bloques"


def test_el_titulo_no_se_duplica_al_fusionar():
    """La fusión concatena textos, y ambos ya traían el encabezado antepuesto."""
    bloques = [
        BloqueTexto("Normalización", 1, es_titulo=True),
        _cuerpo(185, 1),
        _cuerpo(10, 1),
    ]
    frag = fragmentar(bloques)[0]

    assert frag.texto.count("Normalización") == 1


def test_tabla_va_en_su_propio_fragmento():
    """Para un perfil visual la tabla es el recurso que pide la tabla 11.1."""
    bloques = [
        _cuerpo(50, 1),
        BloqueTexto("Canal | Peso\nVisual | 45", pagina=1, tipo="tabla"),
        _cuerpo(50, 1),
    ]
    frags = fragmentar(bloques)

    tablas = [f for f in frags if f.tipo == "tabla"]
    assert len(tablas) == 1
    assert "dato" not in tablas[0].texto, "la tabla no debe mezclarse con prosa"


def test_numeracion_secuencial_sin_huecos():
    """`numero_fragmento` tiene UNIQUE(id_documento, numero) en la tabla 17.7."""
    bloques = [
        BloqueTexto("Tema", 1, es_titulo=True),
        _cuerpo(200, 1),
        _cuerpo(5, 1),
        BloqueTexto("Otro tema", 2, es_titulo=True),
        _cuerpo(200, 2),
    ]
    frags = fragmentar(bloques)

    assert [f.numero for f in frags] == list(range(1, len(frags) + 1))


def test_etiqueta_tematica_cabe_en_la_columna():
    """`etiqueta_tematica` es VARCHAR(100) en la tabla 17.7."""
    titulo_largo = "Unidad " + "muy larga " * 30
    bloques = [BloqueTexto(titulo_largo, 1, es_titulo=True), _cuerpo(60, 1)]

    frag = fragmentar(bloques)[0]

    assert frag.etiqueta_tematica is not None
    assert len(frag.etiqueta_tematica) <= MAX_LARGO_ETIQUETA


def test_documento_vacio_no_produce_fragmentos():
    assert fragmentar([]) == []


def test_solo_titulos_no_produce_fragmentos():
    """Un índice o portada sin cuerpo no aporta material recuperable."""
    bloques = [BloqueTexto(f"Sección {i}", i, es_titulo=True) for i in range(1, 5)]
    assert fragmentar(bloques) == []


def test_fragmento_expone_su_conteo_de_palabras():
    f = FragmentoCrudo(numero=1, texto="una dos tres", pagina_inicio=1, pagina_fin=1)
    assert f.palabras == 3


# --- Extracción desde archivos reales ----------------------------------------


def _escribir_pdf(destino: Path, paginas: list[tuple[str, str]]) -> Path:
    """Genera un PDF con un título grande y un cuerpo chico por página."""
    pymupdf = pytest.importorskip("pymupdf")

    doc = pymupdf.open()
    for titulo, cuerpo in paginas:
        pagina = doc.new_page()
        pagina.insert_text((72, 90), titulo, fontsize=20)
        pagina.insert_textbox((72, 120, 520, 700), cuerpo, fontsize=10)
    doc.save(destino)
    doc.close()
    return destino


def _escribir_pptx(destino: Path, diapos: list[tuple[str, str]]) -> Path:
    pptx = pytest.importorskip("pptx")

    presentacion = pptx.Presentation()
    layout = presentacion.slide_layouts[1]  # Título y contenido
    for titulo, cuerpo in diapos:
        diapo = presentacion.slides.add_slide(layout)
        diapo.shapes.title.text = titulo
        diapo.placeholders[1].text = cuerpo
    presentacion.save(destino)
    return destino


def test_extraer_pdf_detecta_titulos_por_tamano(tmp_path):
    ruta = _escribir_pdf(
        tmp_path / "apunte.pdf",
        [
            ("Normalizacion de bases de datos", "La primera forma normal exige atomicidad. " * 6),
            ("Dependencias funcionales", "Una dependencia funcional relaciona atributos. " * 6),
        ],
    )

    bloques = extraer(ruta)

    titulos = [b.texto for b in bloques if b.es_titulo]
    assert "Normalizacion de bases de datos" in titulos
    assert "Dependencias funcionales" in titulos

    cuerpos = [b for b in bloques if not b.es_titulo]
    assert cuerpos, "debe extraer también el cuerpo"
    assert all(not b.es_titulo for b in cuerpos)


def test_extraer_pdf_conserva_el_numero_de_pagina(tmp_path):
    """Sin la página, la trazabilidad del cap. 8.1 deja de ser auditable."""
    ruta = _escribir_pdf(
        tmp_path / "dos_paginas.pdf",
        [
            ("Pagina uno", "contenido de la primera. " * 8),
            ("Pagina dos", "contenido de la segunda. " * 8),
        ],
    )

    bloques = extraer(ruta)

    assert {b.pagina for b in bloques} == {1, 2}
    primera = next(b for b in bloques if "primera" in b.texto)
    segunda = next(b for b in bloques if "segunda" in b.texto)
    assert primera.pagina == 1
    assert segunda.pagina == 2


def test_extraer_pdf_no_pega_palabras_entre_renglones(tmp_path):
    """Regresión: unir las líneas de un bloque sin separador glutina palabras.

    PyMuPDF entrega una `line` por renglón. Concatenarlas con "" producía
    "parareducir" o "nocontienen" al saltar de renglón, lo que rompe el
    full-text search en español y le entrega texto corrupto al LLM. Los tests
    de estructura pasaban igual: solo se ve inspeccionando el texto extraído.
    """
    texto_largo = (
        "La normalizacion organiza los datos de una base relacional para "
        "reducir la redundancia y mejorar la integridad de la informacion "
        "almacenada en cada una de las tablas del esquema disenado. "
    )
    ruta = _escribir_pdf(tmp_path / "renglones.pdf", [("Normalizacion", texto_largo * 3)])

    cuerpo = " ".join(b.texto for b in extraer(ruta) if not b.es_titulo)

    assert "parareducir" not in cuerpo
    # Toda palabra del cuerpo debe existir en el original: si alguna se pegó con
    # la siguiente, aparecerá un token que no estaba.
    originales = set(texto_largo.split())
    for palabra in cuerpo.split():
        assert palabra in originales, f"token inesperado {palabra!r}: renglones pegados"


def test_extraer_pptx_marca_el_titulo_de_la_diapositiva(tmp_path):
    ruta = _escribir_pptx(
        tmp_path / "clase.pptx",
        [
            ("Arquitectura RAG", "Recupera antes de generar"),
            ("Perfil VARK", "Cuatro canales sensoriales"),
        ],
    )

    bloques = extraer(ruta)

    titulos = [b for b in bloques if b.es_titulo]
    assert [b.texto for b in titulos] == ["Arquitectura RAG", "Perfil VARK"]
    assert [b.pagina for b in titulos] == [1, 2], "la diapositiva es la 'página'"


def test_pptx_separa_cada_vinieta_en_su_bloque(tmp_path):
    """Unir las viñetas produciría un bloque corrido que ya no se puede separar."""
    ruta = _escribir_pptx(
        tmp_path / "vinetas.pptx", [("Canales", "Visual\nAuditivo\nLector\nKinestesico")]
    )

    bloques = extraer(ruta)
    cuerpos = [b.texto for b in bloques if not b.es_titulo]

    assert "Visual" in cuerpos
    assert "Kinestesico" in cuerpos


def test_extraer_rechaza_formato_no_soportado(tmp_path):
    ruta = tmp_path / "apunte.docx"
    ruta.write_text("contenido", encoding="utf-8")

    with pytest.raises(FormatoNoSoportado, match="docx"):
        extraer(ruta)


def test_hash_detecta_el_mismo_archivo_con_otro_nombre(tmp_path):
    """`hash_archivo` es UNIQUE en la tabla 17.6: evita cargar dos veces el mismo apunte."""
    a = tmp_path / "clase1.pdf"
    b = tmp_path / "copia_de_clase1.pdf"
    contenido = b"%PDF-1.4 contenido identico"
    a.write_bytes(contenido)
    b.write_bytes(contenido)
    distinto = tmp_path / "otra.pdf"
    distinto.write_bytes(b"%PDF-1.4 otro contenido")

    assert hash_archivo(a) == hash_archivo(b)
    assert hash_archivo(a) != hash_archivo(distinto)


def test_pipeline_completo_pdf_a_fragmentos(tmp_path):
    """Extracción + fragmentación sobre un archivo real, de punta a punta."""
    ruta = _escribir_pdf(
        tmp_path / "unidad.pdf",
        [
            ("Modelo relacional", "Una tabla representa una relacion matematica. " * 20),
            ("Claves foraneas", "La clave foranea garantiza integridad referencial. " * 20),
        ],
    )

    frags = fragmentar(extraer(ruta))

    assert frags, "el pipeline debe producir fragmentos"
    etiquetas = {f.etiqueta_tematica for f in frags}
    assert "Modelo relacional" in etiquetas
    assert "Claves foraneas" in etiquetas
    for f in frags:
        assert f.pagina_inicio >= 1
        assert f.pagina_fin >= f.pagina_inicio
        assert f.texto.strip()
