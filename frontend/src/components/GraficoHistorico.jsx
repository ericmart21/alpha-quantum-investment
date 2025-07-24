const GraficoHistorico = ({ datos }) => {
  const data = datos.map(item => ({
    name: item.fecha,
    value: item.valor
  }));

  return (
    <LineChart width={500} height={300} data={data}>
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="value" stroke="#8884d8" />
    </LineChart>
  );
};
