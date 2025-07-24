import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { motion } from "framer-motion";

export default function GraficoRentabilidad({ data }) {
  console.log("📊 Datos recibidos en GraficoRentabilidad:", data);

  if (!Array.isArray(data) || data.length === 0) {
    return (
      <motion.p
        className="text-muted"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        No hay datos disponibles para mostrar el gráfico.
      </motion.p>
    );
  }

  const parsedData = data.map((item) => ({
    ...item,
    ganancia: parseFloat(item.ganancia) || 0,
    rentabilidad_pct: parseFloat(item.rentabilidad_pct) || 0,
  }));

  return (
    <motion.div
      style={{ width: "100%", padding: "1rem 0" }}
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
    >
      <h3 className="text-light mb-3">📊 Rentabilidad (€) por Acción</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={parsedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ccc" />
          <XAxis dataKey="nombre" stroke="#fff" />
          <YAxis stroke="#fff" />
          <Tooltip />
          <Legend />
          <Bar dataKey="ganancia" fill="#0dcaf0" name="Ganancia (€)" />
        </BarChart>
      </ResponsiveContainer>

      <h3 className="text-light mt-5 mb-3">📈 Rentabilidad (%) por Acción</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={parsedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ccc" />
          <XAxis dataKey="nombre" stroke="#fff" />
          <YAxis unit="%" stroke="#fff" />
          <Tooltip />
          <Legend />
          <Bar
            dataKey="rentabilidad_pct"
            fill="#ffc107"
            name="Rentabilidad (%)"
          />
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
