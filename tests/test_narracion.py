"""Qué se narra de una cápsula y qué archivos puede dejar (sin base de datos).

Lo que protegen: que la supresión (`/mis-datos/eliminar`) encuentre todos los
audios que dejó el visor. Los tests de punta a punta están en
`test_web_legal.py` y necesitan Postgres.
"""

from pathlib import Path

from studify.config import get_settings
from studify.media import audio
from studify.web import narracion


def test_las_voces_posibles_cubren_las_cuatro_preferencias_y_xtts():
    voces = audio.voces_posibles()

    assert len(set(voces)) == 5
    for genero in ("femenina", "masculina"):
        for modo in ("calidad", "rapida"):
            assert audio.resolver_voz(audio.PreferenciaVoz(genero, modo)) in voces
    assert audio.VozElegida(motor="xtts") in voces


def test_las_voces_posibles_no_dependen_del_motor_configurado(monkeypatch):
    """Con `TTS_MOTOR=xtts` el estudiante igual pudo narrar antes con Kokoro o Piper."""
    antes = audio.voces_posibles()
    monkeypatch.setattr(get_settings(), "tts_motor", "xtts")

    assert audio.voces_posibles() == antes


def test_el_guion_es_la_activacion_y_el_concepto():
    contenido = {"activacion": "¿Qué pasa?", "concepto_central": "Esto pasa.", "ejemplo": {}}

    assert narracion.guion(contenido) == "¿Qué pasa? Esto pasa."


def test_sin_texto_se_narra_el_guion_generico():
    assert narracion.guion(None) == narracion.GUION_POR_DEFECTO
    assert narracion.guion({"activacion": " ", "concepto_central": ""}) == (
        narracion.GUION_POR_DEFECTO
    )


def test_los_archivos_de_un_guion_son_uno_por_voz():
    guion = "¿Qué pasa? Esto pasa."

    nombres = narracion.archivos([guion])

    assert nombres == {f"{audio.huella_de_audio(guion, v)}.wav" for v in audio.voces_posibles()}


def test_el_guion_generico_no_es_de_nadie():
    """Lo comparten todas las cápsulas sin texto: la supresión no lo borra."""
    assert narracion.archivos([narracion.GUION_POR_DEFECTO]) == set()


def test_el_directorio_es_el_que_publica_main_y_no_depende_del_de_trabajo():
    """Antes el visor escribía en una ruta relativa: arrancado desde otra carpeta,
    los audios quedaban donde `/public` no los sirve y la supresión no los busca."""
    from studify import main

    directorio = narracion.DIRECTORIO_AUDIO

    assert directorio.is_absolute()
    assert directorio.parent == Path(main.PUBLIC_DIR)
