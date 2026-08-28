/**
 * Las barras del vector VARK.
 *
 * Un solo componente para el perfil del estudiante y para el promedio de la
 * cohorte en el panel del docente, por la misma razón por la que el backend
 * arma las barras en Python y no en la plantilla: el nombre y el color de cada
 * canal tienen que ser los mismos en los dos gráficos. Con dos componentes
 * distintos, tarde o temprano el canal V se pinta de un color en una pantalla y
 * de otro en la otra.
 *
 * El color viene del servidor (`textos.COLOR_CANAL`), no de una constante local:
 * es la única forma de que no haya dos fuentes de verdad para lo mismo.
 */

import type { BarraCanal } from "../api/types";

export function BarrasVark({ canales }: { canales: BarraCanal[] }) {
  return (
    <div className="flex flex-col gap-4">
      {canales.map((canal) => (
        <div key={canal.canal}>
          <div className="flex justify-between mb-1">
            <span className="font-medium">{canal.nombre}</span>
            <span className="text-muted">{canal.texto}%</span>
          </div>
          <div className="progress-container">
            <div
              className="progress-bar"
              style={{ width: `${canal.ancho}%`, backgroundColor: canal.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
