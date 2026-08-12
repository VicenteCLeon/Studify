"""Llamada al modelo y bucle de reparación (Fase 3 del plan).

El generador no sabe qué es una microcápsula: recibe un `PromptMaestro` ya
ensamblado, pide una respuesta, la pasa por el validador y —si falla— reinyecta
los errores y vuelve a pedirla. Tres intentos como máximo (uno inicial más los
dos reintentos que fija `PLAN_DESARROLLO.md` §3) y después se rinde con un
error explícito.

**Por qué el LLM entra como `ClienteLLM` y no como `OpenAILike` directo.** El
bucle de reparación es la lógica más delicada de la fase y la que más
comportamientos raros tiene que cubrir —JSON truncado, citas inventadas, deriva
al inglés—, y todos ellos son fáciles de provocar con un cliente falso e
imposibles de provocar a demanda contra un modelo real. Con la interfaz de por
medio, `tests/test_generador.py` cubre el bucle completo sin red, sin
`LLM_API_KEY` y sin gastar un peso.

**La tasa de fallo es un resultado del informe, no solo un detalle operativo.**
El criterio de término de la Fase 3 pide «una cápsula válida ≥95% de las veces»
y el bake-off compara «% de JSON válido al primer intento» entre modelos. Por
eso `ResultadoGeneracion` acarrea intentos, latencia y el detalle de qué falló
en cada vuelta, en vez de devolver solo la cápsula.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from studify.config import get_settings
from studify.generation.schemas import Microcapsula
from studify.generation.validator import validar
from studify.rag.orchestrator import PromptMaestro

logger = logging.getLogger(__name__)

Rol = Literal["system", "user", "assistant"]


class ErrorGeneracion(Exception):
    """No se consiguió una cápsula válida dentro de los intentos permitidos.

    Lleva el detalle por intento para que el `502` que devuelve la API diga qué
    falló y para poder tabular los modos de fallo en el informe.
    """

    def __init__(self, mensaje: str, *, errores_por_intento: Sequence[Sequence[str]] = ()):
        super().__init__(mensaje)
        self.errores_por_intento = [list(e) for e in errores_por_intento]


@dataclass(frozen=True, slots=True)
class Mensaje:
    rol: Rol
    contenido: str


class ClienteLLM(Protocol):
    """Lo único que el generador necesita de un modelo."""

    modelo: str

    def responder(self, mensajes: Sequence[Mensaje]) -> str: ...


class ClienteOpenAILike:
    """Cliente real, sobre la API compatible con OpenAI.

    DeepSeek, Qwen y GLM —los tres candidatos del equipo— exponen la misma
    interfaz, así que cambiar de modelo es cambiar `LLM_BASE_URL` y `LLM_MODEL`
    en el `.env`, sin tocar código (decisión de stack, AVANCE.md §2).
    """

    def __init__(
        self,
        *,
        modelo: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        ajustes = get_settings()
        self.modelo = modelo or ajustes.llm_model
        clave = api_key if api_key is not None else ajustes.llm_api_key

        if not clave:
            # Se avisa acá y no cuando el proveedor devuelva 401: el error de
            # autenticación no dice cuál de las dos variables falta.
            raise ErrorGeneracion(
                "falta LLM_API_KEY en el .env: sin credencial no se puede "
                "generar. El resto del motor (contrato, validador y prompt) "
                "funciona y está cubierto por tests sin necesidad de clave."
            )

        # El import va acá dentro para que importar este módulo no arrastre
        # LlamaIndex: los tests del bucle usan un cliente falso y no lo
        # necesitan.
        from llama_index.llms.openai_like import OpenAILike

        extra: dict = {}
        if ajustes.llm_json_mode:
            extra["response_format"] = {"type": "json_object"}

        self._llm = OpenAILike(
            model=self.modelo,
            api_base=base_url if base_url is not None else ajustes.llm_base_url,
            api_key=clave,
            temperature=ajustes.llm_temperature,
            timeout=ajustes.llm_timeout,
            max_tokens=ajustes.llm_max_tokens,
            # Sin esto OpenAILike pega contra el endpoint de completions
            # antiguo, que ninguno de los tres proveedores expone.
            is_chat_model=True,
            additional_kwargs=extra,
        )

    def responder(self, mensajes: Sequence[Mensaje]) -> str:
        from llama_index.core.base.llms.types import ChatMessage

        respuesta = self._llm.chat(
            [ChatMessage(role=m.rol, content=m.contenido) for m in mensajes]
        )
        return respuesta.message.content or ""


@dataclass(slots=True)
class ResultadoGeneracion:
    """La cápsula y cómo costó conseguirla."""

    capsula: Microcapsula
    prompt: PromptMaestro
    modelo: str
    intentos: int
    segundos: float
    metricas: dict[str, object] = field(default_factory=dict)
    errores_por_intento: list[list[str]] = field(default_factory=list)

    @property
    def valida_al_primer_intento(self) -> bool:
        """La métrica que el bake-off compara entre modelos."""
        return self.intentos == 1


def generar(
    prompt: PromptMaestro,
    *,
    cliente: ClienteLLM,
    max_reintentos: int | None = None,
) -> ResultadoGeneracion:
    """Pide la cápsula y la repara hasta conseguirla o agotar los intentos.

    Los fragmentos contra los que se validan las citas salen del propio
    `prompt`, no de un argumento aparte: son por construcción los mismos que se
    inyectaron, que es lo que hace exacta la regla 5.
    """
    ajustes = get_settings()
    reintentos = ajustes.llm_max_repair_attempts if max_reintentos is None else max_reintentos
    total_intentos = reintentos + 1

    mensajes: list[Mensaje] = [
        Mensaje("system", prompt.sistema),
        Mensaje("user", prompt.usuario),
    ]
    errores_por_intento: list[list[str]] = []
    inicio = time.perf_counter()

    for intento in range(1, total_intentos + 1):
        crudo = cliente.responder(mensajes)
        resultado = validar(
            crudo,
            fragmentos=prompt.fragmentos,
            palabras_objetivo=prompt.palabras_objetivo,
        )

        if resultado.es_valida:
            assert resultado.capsula is not None  # lo garantiza `es_valida`
            return ResultadoGeneracion(
                capsula=resultado.capsula,
                prompt=prompt,
                modelo=cliente.modelo,
                intentos=intento,
                segundos=time.perf_counter() - inicio,
                metricas=resultado.metricas,
                errores_por_intento=errores_por_intento,
            )

        errores_por_intento.append(resultado.errores)
        logger.warning(
            "cápsula rechazada (intento %d/%d, modelo %s): %s",
            intento,
            total_intentos,
            cliente.modelo,
            "; ".join(resultado.errores),
        )

        if intento < total_intentos:
            # Se reinyecta la respuesta rechazada junto con el motivo. El modelo
            # necesita ver qué produjo para corregirlo: sin eso, un "acorta el
            # contenido" no tiene referente y suele devolver otro texto igual
            # de largo.
            mensajes.append(Mensaje("assistant", crudo))
            mensajes.append(Mensaje("user", resultado.mensaje_para_reparacion()))

    raise ErrorGeneracion(
        f"no se obtuvo una cápsula válida en {total_intentos} intentos con el "
        f"modelo '{cliente.modelo}'. Último motivo: "
        f"{'; '.join(errores_por_intento[-1])}",
        errores_por_intento=errores_por_intento,
    )
