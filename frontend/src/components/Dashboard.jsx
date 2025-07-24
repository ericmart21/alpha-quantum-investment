import { useEffect, useState } from "react";
import GraficoRentabilidad from "./GraficoRentabilidad.jsx";

export default function Dashboard() {
  const [valorActual, setValorActual] = useState(0);
  const [totalInvertido, setTotalInvertido] = useState(0);
  const [rentabilidad, setRentabilidad] = useState(0);
  const [accionesRentabilidad, setAccionesRentabilidad] = useState(null);
  

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/dashboard-data/")
      .then((r) => r.json())
      .then((data) => {
        setValorActual(data.valor_total_cartera);
        setTotalInvertido(data.total_invertido);
        setRentabilidad(data.rentabilidad_total);
        setAccionesRentabilidad(data.top_3_mejores || []);
      })
      .catch((err) => console.error("❌ Error en fetch:", err));
  }, []);

  return (
    <div>
      <h1 className="mb-4">📊 Panel de Inversión</h1>

      <div className="row mb-5">
        <div className="col-md-4 mb-3">
          <div className="card bg-secondary text-white">
            <div className="card-body">
              <h5 className="card-title">Valor actual</h5>
              <p className="card-text fs-4">{valorActual.toFixed(2)} €</p>
            </div>
          </div>
        </div>

        <div className="col-md-4 mb-3">
          <div className="card bg-secondary text-white">
            <div className="card-body">
              <h5 className="card-title">Total invertido</h5>
              <p className="card-text fs-4">{totalInvertido.toFixed(2)} €</p>
            </div>
          </div>
        </div>

        <div className="col-md-4 mb-3">
          <div className="card bg-secondary text-white">
            <div className="card-body">
              <h5 className="card-title">Rentabilidad total</h5>
              <p className="card-text fs-4">{rentabilidad.toFixed(2)} €</p>
            </div>
          </div>
        </div>
      </div>

      <GraficoRentabilidad data={accionesRentabilidad} />
    </div>
  );
}
