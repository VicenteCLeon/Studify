// Ejecuta las funciones reales del borrador con almacenamiento y formulario
// mínimos. No requiere navegador ni dependencias npm.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../src/studify/web/static/js/app.js"), "utf8");
new vm.Script(source); // Comprueba la sintaxis de todo app.js.
const inicio = source.indexOf("    function save()");
const fin = source.indexOf("    function updateMeta()", inicio);
assert.ok(inicio >= 0 && fin > inicio, "No se encontraron las funciones del borrador");
const funciones = source.slice(inicio, fin);
const memoria = new Map();
const storage = {
  setItem: (key, value) => memoria.set(key, value),
  getItem: (key) => memoria.get(key),
  removeItem: (key) => memoria.delete(key),
};

function formulario(contexto, carrera = "", anterior = "") {
  const pregunta = { name: "q1", value: "a", checked: false };
  const aceptacion = { name: "acepto", value: "si", checked: false };
  const consentimiento = { name: "consiento_genero", value: "si", checked: false };
  const form = {
    dataset: { contextoBorrador: contexto, contextoAnterior: anterior },
    elements: { carrera: { value: carrera }, rango_etario: { value: "" }, genero: { value: "" } },
    querySelectorAll: () => [pregunta, aceptacion, consentimiento].filter((box) => box.checked),
    querySelector: () => pregunta,
  };
  const cargar = new Function("form", "sessionStorage", "VARK_KEY", "NO_SE_GUARDAN",
    "current", "last", funciones + "; return {save, restore};");
  return { form, pregunta, aceptacion, consentimiento,
    ...cargar(form, storage, "draft", ["acepto", "consiento_genero"], 3, 17) };
}

const original = formulario("cuenta-a", "Carrera A");
original.pregunta.checked = true;
original.aceptacion.checked = true;
original.consentimiento.checked = true;
original.form.elements.rango_etario.value = "21 - 23 años";
original.form.elements.genero.value = "Femenino";
original.save();
const guardado = memoria.get("draft");
assert.deepEqual(JSON.parse(guardado).marcadas, ["q1=a"]);
const misma = formulario("cuenta-a");
assert.equal(misma.restore(), 3);
assert.equal(misma.form.elements.carrera.value, "Carrera A");
assert.equal(misma.pregunta.checked, true);

memoria.set("draft", guardado);
const otra = formulario("cuenta-b");
assert.equal(otra.restore(), 0);
assert.equal(otra.form.elements.carrera.value, "");
assert.equal(otra.pregunta.checked, false);
assert.equal(memoria.has("draft"), false);

memoria.set("draft", JSON.stringify({ paso: 3, carrera: "Anterior", marcadas: ["q1=a"] }));
assert.equal(formulario("cuenta-b").restore(), 0);
assert.equal(memoria.has("draft"), false);
memoria.set("draft", guardado);
const continuacion = formulario("cuenta-google", "", "cuenta-a");
assert.equal(continuacion.restore(), 3);
assert.equal(continuacion.form.elements.carrera.value, "Carrera A");
assert.equal(continuacion.pregunta.checked, true);
assert.equal(continuacion.form.elements.rango_etario.value, "21 - 23 años");
assert.equal(continuacion.form.elements.genero.value, "Femenino");
assert.equal(continuacion.aceptacion.checked, false);
assert.equal(continuacion.consentimiento.checked, false);
continuacion.save();
assert.equal(JSON.parse(memoria.get("draft")).contexto, "cuenta-google");
assert.deepEqual(JSON.parse(memoria.get("draft")).marcadas, ["q1=a"]);
assert.equal(formulario("cuenta-google").restore(), 3);
// Punto 2a: elegir Control en el acceso descarta el borrador del cuestionario.
const inicioGrupo = source.indexOf("  function olvidarBorradorSiControl(");
const finGrupo = source.indexOf("  function initGrupoBorrador(", inicioGrupo);
assert.ok(inicioGrupo >= 0 && finGrupo > inicioGrupo, "No se encontró olvidarBorradorSiControl");
const olvidar = new Function("VARK_KEY", source.slice(inicioGrupo, finGrupo) +
  "; return olvidarBorradorSiControl;")("draft");
function acceso(rol) {
  return { querySelector: () => (rol ? { value: rol } : null) };
}
memoria.set("draft", guardado);
assert.equal(olvidar(acceso("estudiante"), storage), false);
assert.equal(memoria.has("draft"), true);
assert.equal(olvidar(acceso(null), storage), false);
assert.equal(memoria.has("draft"), true);
assert.equal(olvidar(acceso("control"), storage), true);
assert.equal(memoria.has("draft"), false);
console.log("7 comprobaciones correctas: sintaxis, borrador propio, aislamiento, legado, continuidad Google, migración de contexto y descarte al elegir Control.");
