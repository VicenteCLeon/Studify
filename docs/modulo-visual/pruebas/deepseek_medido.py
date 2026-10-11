"""Cliente LLM del proyecto, con cuenta de tokens y tope de gasto.

`ClienteOpenAILike` (el cliente real de `generation/generator.py`) devuelve solo
el texto de la respuesta. Para validar el paso LLM del módulo Visual hace falta
además saber cuánto costó cada llamada, así que `ClienteMedido` lo hereda —misma
temperatura, mismo modo JSON, mismo `max_tokens`— y solo cambia `responder` para
leer el `usage` que DeepSeek devuelve y anotarlo en un libro de gastos.

El libro vive en `resultados/llm/gasto_deepseek.json` y es acumulativo entre
scripts: el tope es de la tarea completa, no de cada corrida.

**El tope se comprueba antes de llamar**, con el peor caso (toda la entrada sin
caché, `max_tokens` completos de salida, tarifa punta). Si esa llamada pudiera
pasar el tope, se levanta `TopeSuperado` y no se llama.

Tarifas de `deepseek-flash` leídas el 10-oct-2026 en
https://api-docs.deepseek.com/quick_start/pricing (USD por millón de tokens):

    entrada con caché   0,003 valle · 0,006 punta
    entrada sin caché   0,15  valle · 0,30  punta
    salida              0,60  valle · 1,20  punta

Punta: 01:00–04:00 y 06:00–10:00 UTC de lunes a viernes. Fines de semana y
feriados chinos son valle. Los feriados no se modelan: en un feriado este módulo
sobrestima el costo, nunca lo subestima.
"""

import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from studify.config import get_settings
from studify.generation.generator import ClienteOpenAILike, Mensaje

AQUI = Path(__file__).resolve().parent
LIBRO = AQUI / "resultados" / "llm" / "gasto_deepseek.json"

# Topes autorizados por el equipo, uno por tarea. Cada fila del libro dice a cuál
# pertenece; las que no lo dicen son de la primera, la validación del paso LLM.
TOPES_USD = {"validacion": 0.10, "migracion": 0.05}
TOPE_USD = TOPES_USD["validacion"]

# USD por millón de tokens: (valle, punta).
TARIFA = {
    "entrada_cache": (0.003, 0.006),
    "entrada": (0.15, 0.30),
    "salida": (0.60, 1.20),
}

# Sin tokenizador a mano, el peor caso de la entrada se estima por caracteres.
# El español ronda los 3 a 4 caracteres por token; 2 deja margen de sobra.
CARACTERES_POR_TOKEN_PESIMISTA = 2


class TopeSuperado(Exception):
    """La próxima llamada podría pasar el tope de gasto autorizado."""


def es_punta(cuando: datetime) -> bool:
    if cuando.weekday() >= 5:
        return False
    hora = cuando.hour + cuando.minute / 60
    return 1 <= hora < 4 or 6 <= hora < 10


def costo(entrada: int, entrada_cache: int, salida: int, *, punta: bool) -> float:
    k = 1 if punta else 0
    return (
        entrada * TARIFA["entrada"][k]
        + entrada_cache * TARIFA["entrada_cache"][k]
        + salida * TARIFA["salida"][k]
    ) / 1_000_000


def leer_libro() -> list[dict]:
    if not LIBRO.exists():
        return []
    return json.loads(LIBRO.read_text(encoding="utf-8"))


def gastado(libro: list[dict] | None = None, *, tarea: str | None = None) -> float:
    """Lo gastado hasta ahora, a la tarifa que rigió en cada llamada.

    Con `tarea`, solo lo de esa tarea; sin ella, todo el libro.
    """
    filas = leer_libro() if libro is None else libro
    return sum(
        f["costo_usd"] for f in filas if tarea is None or f.get("tarea", "validacion") == tarea
    )


class ClienteMedido(ClienteOpenAILike):
    """El cliente del proyecto, que además anota tokens, segundos y costo."""

    def __init__(
        self,
        *,
        etiqueta: str = "",
        modelo: str | None = None,
        thinking: str | None = None,
        tarea: str = "validacion",
    ) -> None:
        super().__init__(modelo=modelo)
        self.etiqueta = etiqueta
        self.tarea = tarea
        if thinking is not None:
            # Por defecto manda `LLM_THINKING`, como en producción. Esto lo cambia
            # solo para este cliente, para comparar configuraciones en una misma
            # corrida: `""` no envía el parámetro, que era el comportamiento
            # anterior a la migración.
            extra = {k: v for k, v in self._llm.additional_kwargs.items() if k != "extra_body"}
            if thinking:
                extra["extra_body"] = {"thinking": {"type": thinking}}
            self._llm.additional_kwargs = extra
        # Lo que de verdad viaja en la petición: "enabled", "disabled" o "" (nada).
        enviado = self._llm.additional_kwargs.get("extra_body", {}).get("thinking", {})
        self.thinking = enviado.get("type", "")
        # Las llamadas de este cliente, en orden. El libro en disco las tiene todas.
        self.llamadas: list[dict] = []

    def responder(self, mensajes: Sequence[Mensaje]) -> str:
        from llama_index.core.base.llms.types import ChatMessage

        ajustes = get_settings()
        libro = leer_libro()
        caracteres = sum(len(m.contenido) for m in mensajes)
        peor_caso = costo(
            caracteres // CARACTERES_POR_TOKEN_PESIMISTA, 0, ajustes.llm_max_tokens, punta=True
        )
        tope, llevamos = TOPES_USD[self.tarea], gastado(libro, tarea=self.tarea)
        if llevamos + peor_caso > tope:
            raise TopeSuperado(
                f"llevamos US${llevamos:.4f} en «{self.tarea}» y esta llamada podría costar "
                f"hasta US${peor_caso:.4f}: pasaría el tope de US${tope:.2f}"
            )

        cuando = datetime.now(UTC)
        inicio = time.perf_counter()
        respuesta = self._llm.chat([ChatMessage(role=m.rol, content=m.contenido) for m in mensajes])
        segundos = time.perf_counter() - inicio

        crudo = respuesta.raw
        datos = crudo if isinstance(crudo, dict) else crudo.model_dump()
        uso = datos.get("usage") or {}
        total_entrada = int(uso.get("prompt_tokens") or 0)
        entrada_cache = int(uso.get("prompt_cache_hit_tokens") or 0)
        salida = int(uso.get("completion_tokens") or 0)
        detalle_salida = uso.get("completion_tokens_details") or {}
        razonamiento = int(detalle_salida.get("reasoning_tokens") or 0)
        opciones = datos.get("choices") or [{}]

        fila = {
            "cuando_utc": cuando.isoformat(timespec="seconds"),
            "etiqueta": self.etiqueta,
            "modelo_pedido": self.modelo,
            "modelo_respondido": datos.get("model"),
            "tarea": self.tarea,
            "thinking": self.thinking,
            "max_tokens": ajustes.llm_max_tokens,
            "tokens_entrada": total_entrada,
            "tokens_entrada_cache": entrada_cache,
            "tokens_salida": salida,
            "tokens_razonamiento": razonamiento,
            "fin": opciones[0].get("finish_reason"),
            "segundos": round(segundos, 2),
            "tarifa": "punta" if es_punta(cuando) else "valle",
            "costo_usd": costo(
                total_entrada - entrada_cache, entrada_cache, salida, punta=es_punta(cuando)
            ),
            # Lo que habría costado en horario punta: la cifra prudente para presupuestar.
            "costo_usd_punta": costo(
                total_entrada - entrada_cache, entrada_cache, salida, punta=True
            ),
            "uso_sin_datos": not uso,
        }
        self.llamadas.append(fila)
        libro.append(fila)
        LIBRO.parent.mkdir(parents=True, exist_ok=True)
        LIBRO.write_text(json.dumps(libro, ensure_ascii=False, indent=2), encoding="utf-8")
        return respuesta.message.content or ""
