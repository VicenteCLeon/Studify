| Corrida | Validación | Tipo | Etiquetas en el material | Posibles términos inventados | Relaciones con respaldo | Sin respaldo | Ortografía | Tokens (entrada + salida) | Costo (US$) | Segundos |
|---|---|---|---|---|---|---|---|--:|--:|--:|
| `PROG-U1-01_c1` | 1 reparación | `mapa_conceptual` | 7 literal + 0 casi, de 7 | — | 6 oración + 0 fragmento, de 6 | — | sin problemas | 5536 + 2443 | 0.00183 | 8.9 |
| `PROG-U1-01_c2` | a la primera | `mapa_conceptual` | 7 literal + 0 casi, de 7 | — | 6 oración + 0 fragmento, de 6 | — | sin problemas | 2117 + 684 | 0.00045 | 2.6 |
| `PROG-U1-01_c3` | a la primera | `mapa_conceptual` | 6 literal + 0 casi, de 6 | — | 0 oración + 5 fragmento, de 5 | — | sin problemas | 2117 + 557 | 0.00037 | 2.2 |
| `PROG-U1-02_c1` | 1 reparación | `jerarquia` | 6 literal + 0 casi, de 6 | — | 1 oración + 4 fragmento, de 5 | — | sin problemas | 4969 + 1139 | 0.00105 | 4.9 |
| `PROG-U1-02_c2` | 1 reparación | `jerarquia` | 6 literal + 0 casi, de 6 | — | 1 oración + 4 fragmento, de 5 | — | sin problemas | 4868 + 960 | 0.00065 | 4.6 |
| `PROG-U1-02_c3` | 1 reparación | `jerarquia` | 3 literal + 2 casi, de 5 | — | 0 oración + 4 fragmento, de 4 | — | sin problemas | 4926 + 1016 | 0.00069 | 4.5 |
| `BD-U3-01_c1` | a la primera | `flujo` | 5 literal + 1 casi, de 6 | — | 0 oración + 3 fragmento, de 7 | «Atomicidad de Atributos —se corrige con→ Paso a Paso»; «Eliminación de Grupos Repetitivos —se corrige con→ Paso a Paso»; «Clave Primaria Definida —se corrige con→ Paso a Paso»; «Paso a Paso —produce→ Tabla Normalizada» | ««unívoca» difiere del material, que escribe ['univoca']» | 2196 + 702 | 0.00075 | 2.9 |
| `BD-U3-01_c2` | a la primera | `mapa_conceptual` | 5 literal + 0 casi, de 5 | — | 0 oración + 3 fragmento, de 4 | «Primera Forma Normal —se aplica mediante→ Paso a Paso» | ««unívoca» difiere del material, que escribe ['univoca']» | 2196 + 522 | 0.00034 | 2.4 |
| `BD-U3-01_c3` | a la primera | `mapa_conceptual` | 5 literal + 1 casi, de 6 | — | 0 oración + 4 fragmento, de 4 | — | ««unívoca» difiere del material, que escribe ['univoca']» | 2196 + 588 | 0.00038 | 2.6 |
| `BD-U3-02_c1` | a la primera | `mapa_conceptual` | 4 literal + 1 casi, de 5 | — | 1 oración + 3 fragmento, de 4 | — | sin problemas | 2400 + 527 | 0.00068 | 2.6 |
| `BD-U3-02_c2` | a la primera | `mapa_conceptual` | 4 literal + 1 casi, de 5 | — | 1 oración + 3 fragmento, de 4 | — | sin problemas | 2400 + 528 | 0.00036 | 2.4 |
| `BD-U3-02_c3` | a la primera | `flujo` | 1 literal + 3 casi, de 4 | — | 0 oración + 2 fragmento, de 3 | «Dependencia Funcional —se ejemplifica con→ Ejemplo RUT» | sin problemas | 2400 + 434 | 0.00030 | 2.4 |

| Corrida | Nodos | Grafo conexo | Relaciones que dibuja el render | Rótulos superpuestos | Detalles repetidos | `fuentes` | Elegida |
|---|--:|:-:|:-:|--:|--:|---|:-:|
| `PROG-U1-01_c1` | 7 | sí | 6 de 6 | 0 | 0 | 1, 2, 3, 4, 5 |  |
| `PROG-U1-01_c2` | 7 | sí | 6 de 6 | 0 | 0 | 1, 2, 3 | ✔ |
| `PROG-U1-01_c3` | 6 | sí | 5 de 5 | 0 | 0 | 1, 2, 3, 4, 5 |  |
| `PROG-U1-02_c1` | 6 | sí | 5 de 5 | 0 | 1 | 6, 7 |  |
| `PROG-U1-02_c2` | 6 | sí | 5 de 5 | 0 | 0 | 6, 7 | ✔ |
| `PROG-U1-02_c3` | 5 | sí | 4 de 4 | 0 | 0 | 6, 7, 8 |  |
| `BD-U3-01_c1` | 6 | sí | 3 de 7 | 0 | 0 | 12, 13, 14, 15, 16, 17 |  |
| `BD-U3-01_c2` | 5 | sí | 4 de 4 | 1 | 0 | 12, 16 | ✔ |
| `BD-U3-01_c3` | 6 | **no** | 4 de 4 | 0 | 0 | 12, 16 |  |
| `BD-U3-02_c1` | 5 | sí | 4 de 4 | 3 | 0 | 18, 22 |  |
| `BD-U3-02_c2` | 5 | sí | 4 de 4 | 3 | 0 | 18, 22 |  |
| `BD-U3-02_c3` | 4 | sí | 1 de 3 | 0 | 0 | 18, 19, 20, 21, 22, 23 |  |
