"""Tests del motor VARK (Fase 1).

Las aserciones no son inventadas: cada bloque contrasta contra una afirmación
concreta del informe (cap. 10, 11.1, 11.2, 16.4). Cuando el informe describe un
comportamiento en prosa pero no da el número exacto, se testea la propiedad
cualitativa que sí afirma, no un valor sacado del propio código.

No requieren Postgres: el motor VARK es puro y se calcula antes de persistir.
"""

from decimal import Decimal

import pytest

from studify.vark.hierarchy import derivar
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import (
    ErrorDiagnosticoVacio,
    PerfilVark,
    Seleccion,
    acumular_puntajes,
    calificar,
)
from studify.vark.weighting import calcular_pesos

D = Decimal


def perfil(v: int | str, a: int | str, r: int | str, k: int | str) -> PerfilVark:
    return PerfilVark(v=D(str(v)), a=D(str(a)), r=D(str(r)), k=D(str(k)))


# --- Cap. 10: calificación --------------------------------------------------


def test_acumula_frecuencia_absoluta_por_canal():
    selecciones = [
        Seleccion(1, "a", "V"),
        Seleccion(1, "b", "K"),  # el cap. 10 permite marcar varias por ítem
        Seleccion(2, "c", "K"),
        Seleccion(3, "a", "A"),
    ]
    puntajes = acumular_puntajes(selecciones)

    assert (puntajes.v, puntajes.a, puntajes.r, puntajes.k) == (1, 1, 0, 2)
    assert puntajes.total == 4


def test_seleccion_multiple_en_un_item_cuenta_para_ambos_canales():
    """Cap. 10: la selección múltiple es explícitamente parte del instrumento."""
    _, p = calificar([Seleccion(1, "a", "V"), Seleccion(1, "b", "K")])
    assert p.v == p.k == D("50.00")


def test_items_en_blanco_no_rompen_la_normalizacion():
    """Cap. 10: dejar ítems sin responder es válido."""
    _, p = calificar([Seleccion(5, "a", "R")])
    assert p.r == D("100.00")
    assert p.total == D("100")


def test_diagnostico_sin_selecciones_es_error_explicito():
    """0/0 no tiene vector porcentual; debe fallar fuerte, no devolver ceros."""
    with pytest.raises(ErrorDiagnosticoVacio):
        calificar([])


def test_num_pregunta_fuera_de_rango_se_rechaza():
    with pytest.raises(ValueError, match="entre 1 y 16"):
        Seleccion(17, "a", "V")


def test_canal_invalido_se_rechaza():
    with pytest.raises(ValueError, match="canal debe ser"):
        Seleccion(1, "a", "X")


# --- Cap. 11.2: el vector porcentual suma 100 exacto ------------------------


@pytest.mark.parametrize(
    "puntajes",
    [
        (1, 1, 1, 0),  # 33.33 × 3 → sumaría 99.99 sin corrección
        (1, 1, 1, 1),
        (7, 3, 2, 4),
        (1, 0, 0, 2),
        (5, 5, 5, 1),
        (0, 0, 0, 3),
    ],
)
def test_porcentajes_siempre_suman_100_exacto(puntajes):
    """Cap. 11.2 exige p_V + p_A + p_R + p_K = 100 como igualdad estricta.

    El CHECK de la tabla `diagnostico_vark` depende de esto, así que un
    desajuste de redondeo aquí se transformaría en un fallo de inserción.
    """
    selecciones = [
        Seleccion(min(i + 1, 16), "a", canal)
        for canal, n in zip("VARK", puntajes, strict=True)
        for i in range(n)
    ]
    _, p = calificar(selecciones)
    assert p.total == D("100")


def test_reparto_del_residuo_favorece_al_resto_mayor():
    """{1,1,1,0}: tres canales a 33.33 y 0.01 de residuo.

    El método del resto mayor debe asignárselo a un canal con parte truncada,
    nunca al canal en cero.
    """
    _, p = calificar(
        [Seleccion(1, "a", "V"), Seleccion(2, "a", "A"), Seleccion(3, "a", "R")]
    )
    assert p.total == D("100")
    assert p.k == D("0.00")
    assert sorted([p.v, p.a, p.r]) == [D("33.33"), D("33.33"), D("33.34")]


# --- Cap. 11.2: fórmulas C_* ------------------------------------------------


@pytest.mark.parametrize(
    "vector",
    [(45, 20, 15, 20), (25, 20, 20, 35), (100, 0, 0, 0), (25, 25, 25, 25)],
)
def test_pesos_suman_100(vector):
    """Los coeficientes de cada canal suman 1.00, así que los C_* suman 100.

    Es la propiedad que hace interpretables los pesos como reparto del énfasis
    instruccional; si alguien edita la matriz de coeficientes, este test lo
    detecta.
    """
    pesos = calcular_pesos(perfil(*vector))
    assert pesos.total == D("100.00")


def test_perfil_visual_del_informe_prioriza_lo_visual():
    """Cap. 11.2: «{45%V, 20%A, 15%R, 20%K} priorizará recursos visuales,
    manteniendo componentes prácticos y narrativos secundarios»."""
    pesos = calcular_pesos(perfil(45, 20, 15, 20))
    assert pesos.visual > pesos.narrativo
    assert pesos.visual > pesos.practico


def test_perfil_kinestesico_del_informe_se_orienta_a_lo_practico():
    """Cap. 11.2: «{25%V, 20%A, 20%R, 35%K} se orientará principalmente a la
    aplicación práctica, conservando apoyo visual moderado»."""
    visual = calcular_pesos(perfil(45, 20, 15, 20))
    kines = calcular_pesos(perfil(25, 20, 20, 35))

    # Más práctico que el perfil visual, y su propio apoyo visual baja.
    assert kines.practico > visual.practico
    assert kines.visual < visual.visual


# --- Cap. 11.1: reglas de decisión ------------------------------------------


def test_pv_sobre_40_exige_dos_recursos_visuales():
    """Tabla 11.1, fila 1: «p_V ≥ 40% → al menos dos recursos visuales»."""
    assert aplicar_reglas(perfil(45, 20, 15, 20)).recursos_visuales == 2
    assert aplicar_reglas(perfil(40, 20, 20, 20)).recursos_visuales == 2


def test_pv_entre_25_y_40_exige_un_recurso_visual():
    """Tabla 11.1, fila 2: «25% ≤ p_V < 40% → al menos un recurso visual»."""
    assert aplicar_reglas(perfil(25, 25, 25, 25)).recursos_visuales == 1
    assert aplicar_reglas(perfil("39.99", "20.01", 20, 20)).recursos_visuales == 1


def test_pv_bajo_25_no_exige_recursos_visuales():
    assert aplicar_reglas(perfil(15, 30, 25, 30)).recursos_visuales == 0


def test_pk_sobre_40_exige_los_tres_componentes_practicos():
    """Tabla 11.1, fila 5: ejemplo aplicado + paso a paso + "inténtalo tú"."""
    config = aplicar_reglas(perfil(20, 20, 15, 45))
    assert config.componentes_practicos == 3
    assert {"ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"} <= set(
        config.directivas
    )


def test_pr_sobre_40_prioriza_densidad_textual_y_glosario():
    """Tabla 11.1, fila 3."""
    config = aplicar_reglas(perfil(10, 20, 50, 20))
    assert {"encabezados_jerarquicos", "definiciones_exactas", "glosario"} <= set(
        config.directivas
    )
    assert config.tono_narrativo == "formal"


def test_pa_sobre_40_activa_tono_conversacional():
    """Tabla 11.1, fila 4."""
    config = aplicar_reglas(perfil(10, 50, 20, 20))
    assert {"tono_oral", "analogias_cotidianas", "preguntas_reflexivas"} <= set(
        config.directivas
    )
    assert config.tono_narrativo == "oral"


def test_palabras_texto_siempre_dentro_del_rango_del_informe():
    """Cap. 11.1: 150–300 palabras. El CHECK de la tabla 17.4 lo replica."""
    for vector in [(100, 0, 0, 0), (0, 0, 100, 0), (25, 25, 25, 25), (0, 0, 0, 100)]:
        assert 150 <= aplicar_reglas(perfil(*vector)).palabras_texto <= 300


def test_perfil_lector_puro_pide_mas_palabras_que_visual_puro():
    """C_texto es máximo en R (0.75) y mínimo en V (0.40)."""
    assert aplicar_reglas(perfil(0, 0, 100, 0)).palabras_texto == 300
    assert aplicar_reglas(perfil(100, 0, 0, 0)).palabras_texto == 150


def test_ningun_perfil_queda_sin_directivas_estructurales():
    """Una cápsula sin directivas sale genérica: es el riesgo declarado en §5
    de PLAN_DESARROLLO.md."""
    for vector in [
        (25, 25, 25, 25),
        (30, 30, 20, 20),
        (100, 0, 0, 0),
        (0, 100, 0, 0),
        (0, 0, 100, 0),
        (0, 0, 0, 100),
        (35, 35, 15, 15),
    ]:
        assert aplicar_reglas(perfil(*vector)).directivas


def test_perfil_multimodal_recibe_las_cuatro_familias_de_directivas():
    """Regla 7: «genera una cápsula equilibrada, integrando texto, apoyo
    visual, explicación narrativa y actividad práctica».

    Caso de regresión: {33.34V, 33.33A, 0R, 33.33K} activa además la regla 2
    (p_V ≥ 25%). Si la rama multimodal solo se aplicara cuando ninguna otra
    regla disparó, este perfil se quedaría con un único recurso visual como
    toda instrucción.
    """
    config = aplicar_reglas(perfil("33.34", "33.33", 0, "33.33"))

    assert config.jerarquia.es_multimodal
    assert {
        "estructura_jerarquica",
        "analogias_cotidianas",
        "definiciones_exactas",
        "ejemplo_resuelto",
    } <= set(config.directivas)


def test_directivas_no_tienen_duplicados():
    """El prompt no debe repetir la misma instrucción estructural."""
    for vector in [(25, 25, 25, 25), ("33.34", "33.33", 0, "33.33"), (45, 20, 15, 20)]:
        directivas = aplicar_reglas(perfil(*vector)).directivas
        assert len(directivas) == len(set(directivas))


def test_audio_activo_queda_fuera_de_alcance():
    """Decisión 2 de PLAN_DESARROLLO.md §6: no hay TTS en el stack del cap. 14."""
    assert aplicar_reglas(perfil(0, 100, 0, 0)).audio_activo is False


# --- Cap. 17.2 / 11.1: jerarquía de canales ---------------------------------


def test_diferencia_menor_a_10_puntos_es_bimodal():
    """Tabla 11.1, fila 6: «dos dimensiones con diferencia ≤ 10 puntos»."""
    j = derivar(perfil(10, 42, 10, 38))
    assert j.es_bimodal
    assert j.canal_primario == "A"
    assert j.canal_secundario == "K"


def test_diferencia_mayor_a_10_puntos_es_unimodal():
    j = derivar(perfil(5, 60, 15, 20))
    assert j.es_unimodal
    assert j.canal_primario == "A"


def test_tres_dimensiones_sobre_20_es_multimodal():
    """Tabla 11.1, fila 7: «tres o más dimensiones sobre el 20%»."""
    j = derivar(perfil(25, 25, 25, 25))
    assert j.es_multimodal
    assert len(j.canales_activos) == 4
    assert aplicar_reglas(perfil(25, 25, 25, 25)).tono_narrativo == "mixto"


def test_canal_en_el_borde_exacto_del_20_no_cuenta_como_activo():
    """La regla 7 dice «sobre el 20%», leído como estrictamente mayor.

    {0V, 20A, 20R, 60K} está claramente dominado por K; con el criterio
    inclusivo (≥ 20) quedaría marcado multimodal solo porque dos canales tocan
    el borde.
    """
    j = derivar(perfil(0, 20, 20, 60))
    assert not j.es_multimodal
    assert j.canal_primario == "K"


def test_canal_dominante_lejano_deja_el_perfil_unimodal():
    """Los canales activos se miden **respecto del máximo**, no contra un piso fijo.

    {0V, 21A, 21R, 58K} tiene tres dimensiones sobre el 20%, pero A y R están a
    37 puntos de K. Con el criterio anterior (fila 7 de la tabla 11.1 usada para
    etiquetar) el perfil quedaba marcado multimodal pese a estar dominado con
    claridad por K. Con el criterio de "empate o diferencia mínima" del cap. 10
    queda unimodal K, que es lo correcto.
    """
    config = aplicar_reglas(perfil(0, 21, 21, 58))

    assert config.jerarquia.es_unimodal
    assert config.jerarquia.etiqueta == "K"
    assert config.tono_narrativo == "practico"
    assert {"ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"} <= set(
        config.directivas
    )


def test_tres_canales_a_diferencia_minima_son_multimodal():
    """«2 o más canales empatados o con diferencia mínima» → multimodal."""
    j = derivar(perfil(30, 28, 26, 16))

    assert j.es_multimodal
    assert j.canales_activos == ("V", "A", "R")
    assert j.etiqueta == "A+R+V"
    assert j.jerarquia == "V→A→R"


def test_perfil_plano_sin_dominante_si_recibe_tono_mixto():
    """"Mixto" queda reservado para los perfiles genuinamente equilibrados."""
    assert aplicar_reglas(perfil(25, 25, 25, 25)).tono_narrativo == "mixto"


def test_etiqueta_bimodal_usa_orden_alfabetico_como_la_tabla_16_2():
    """El informe tabula los perfiles como A+K, K+R, A+R… (orden alfabético)."""
    assert derivar(perfil(10, 42, 10, 38)).etiqueta == "A+K"
    assert derivar(perfil(10, 10, 42, 38)).etiqueta == "K+R"


def test_jerarquia_usa_orden_por_puntaje_como_el_cap_16_4():
    """Cap. 16.4 describe el perfil predominante como K→A: K primero por tener
    mayor promedio (7,96 contra 6,57), aunque la etiqueta sea A+K."""
    j = derivar(perfil(10, 38, 10, 42))
    assert j.etiqueta == "A+K"
    assert j.jerarquia == "K→A"
    assert j.canal_primario == "K"


def test_jerarquia_es_determinista_ante_empate():
    """Un empate debe resolverse siempre igual, o los tests serían intermitentes."""
    assert derivar(perfil(25, 25, 25, 25)).jerarquia == derivar(
        perfil(25, 25, 25, 25)
    ).jerarquia


def test_perfil_por_defecto_del_sistema_es_k_a():
    """Cap. 16.4: la moda de Ing. Informática (K=7,96 / A=6,57) fija el
    parámetro por defecto del prompt como bimodal K→A.

    Se usan los promedios reales del informe normalizados a porcentaje.
    """
    total = D("7.96") + D("6.57") + D("5.17") + D("3.65")
    prom = PerfilVark(
        v=(D("3.65") / total * 100).quantize(D("0.01")),
        a=(D("6.57") / total * 100).quantize(D("0.01")),
        r=(D("5.17") / total * 100).quantize(D("0.01")),
        k=(D("7.96") / total * 100).quantize(D("0.01")),
    )
    j = derivar(prom)

    assert j.canal_primario == "K"
    assert j.canal_secundario == "A"
    assert j.jerarquia.startswith("K→A")
