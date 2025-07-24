// src/services/api.js

export async function fetchDashboardData() {
  const response = await fetch("/api/dashboard-data/");
  if (!response.ok) {
    throw new Error("Error al obtener los datos del dashboard");
  }
  return await response.json();
}

useEffect(() => {
  fetch("api/dashboard-data/")
    .then(res => res.json())
    .then(data => {
      setValorActual(data.valor_actual);
      setTotalInvertido(data.total_invertido);
      setRentabilidad(data.rentabilidad);
      // otros sets: data.transacciones, data.historico, etc.
    });
}, []);

export async function fetchCartera() {
  const response = await fetch("/api/cartera/");
  if (!response.ok) {
    throw new Error("Error al obtener la cartera");
  }
  return await response.json();
}
