import React, { useEffect, useState } from "react";
import { fetchCartera } from "../services/api";

function Cartera() {
  const [acciones, setAcciones] = useState([]);

  useEffect(() => {
    fetchCartera().then(setAcciones);
  }, []);

  return (
    <div className="container mt-4">
      <h2>Mi Cartera</h2>
      <table className="table table-dark table-striped">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Ticker</th>
            <th>Cantidad</th>
            <th>Precio Compra</th>
            <th>Precio Actual</th>
            <th>Ganancia (€)</th>
            <th>Rentabilidad (%)</th>
          </tr>
        </thead>
        <tbody>
          {acciones.map((accion) => (
            <tr key={accion.id}>
              <td>{accion.nombre}</td>
              <td>{accion.ticker}</td>
              <td>{accion.cantidad}</td>
              <td>{accion.precio_compra.toFixed(2)} €</td>
              <td>{accion.precio_actual.toFixed(2)} €</td>
              <td>{accion.ganancia.toFixed(2)} €</td>
              <td>{accion.rentabilidad_pct.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default Cartera;