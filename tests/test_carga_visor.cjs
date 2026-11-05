// Punto 2b: duración mínima de la capa de carga en el visor.
// Ejecuta la función real de app.js con relojes y marcas falsas; no requiere
// navegador ni dependencias npm.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../src/studify/web/static/js/app.js"), "utf8");
new vm.Script(source); // Comprueba la sintaxis de todo app.js.
const inicio = source.indexOf("  function restanteDeCarga(");
const fin = source.indexOf("  function initCargaVisor(", inicio);
assert.ok(inicio >= 0 && fin > inicio, "No se encontró restanteDeCarga");
const restanteDeCarga = new Function(source.slice(inicio, fin) + "; return restanteDeCarga;")();

const MINIMO = 4000;
const AHORA = 1_000_000;
const marca = (inicioMs) => JSON.stringify({ inicio: inicioMs, codigo: "BD-U3-01", tema: "2FN" });

// Sin instante guardado (enlace directo, recarga o «atrás»): sin animación.
assert.equal(restanteDeCarga(null, AHORA, MINIMO), 0);
assert.equal(restanteDeCarga(undefined, AHORA, MINIMO), 0);
assert.equal(restanteDeCarga("", AHORA, MINIMO), 0);
// Marcas dañadas o ajenas: sin animación.
assert.equal(restanteDeCarga("no es json", AHORA, MINIMO), 0);
assert.equal(restanteDeCarga(JSON.stringify({ codigo: "x" }), AHORA, MINIMO), 0);
assert.equal(restanteDeCarga(JSON.stringify({ inicio: "ayer" }), AHORA, MINIMO), 0);
// Desde el caché la página llega en 300 ms: falta completar el mínimo.
assert.equal(restanteDeCarga(marca(AHORA - 300), AHORA, MINIMO), 3700);
// La generación tardó más que el mínimo: se muestra de inmediato.
assert.equal(restanteDeCarga(marca(AHORA - 4000), AHORA, MINIMO), 0);
assert.equal(restanteDeCarga(marca(AHORA - 15000), AHORA, MINIMO), 0);
// Reloj adelantado o marca del futuro: no se espera más del mínimo.
assert.equal(restanteDeCarga(marca(AHORA + 60000), AHORA, MINIMO), 0);
// Mínimo desactivado.
assert.equal(restanteDeCarga(marca(AHORA - 300), AHORA, 0), 0);
console.log("5 comprobaciones correctas: sintaxis, sin instante, marcas dañadas, mínimo desde caché y espera ya cumplida.");
