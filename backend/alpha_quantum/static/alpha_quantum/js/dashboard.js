// backend/alpha_quantum/static/alpha_quantum/js/dashboard.js
(async function(){
  const res = await fetch('/api/dashboard-data/');
  const data = await res.json();

  // KPIs
  const fmt = n => typeof n === 'number' ? n.toLocaleString('es-ES', {style:'currency', currency:'EUR'}) : '—';
  document.getElementById('kpi-valor').textContent        = fmt(data.valor_total || data.total_value);
  document.getElementById('kpi-rentabilidad').textContent = fmt(data.rentabilidad || data.net_profit);
  document.getElementById('kpi-invertido').textContent    = fmt(data.total_invertido || data.invested);

  // Evolución (línea)
  const hist = (data.historico || data.history || []).map(p => ({ x: p.fecha || p.date, y: p.valor || p.value }));
  const ctx1 = document.getElementById('lineChart');
  const lineChart = new Chart(ctx1, {
    type:'line',
    data:{ datasets:[{ label:'Ganancia (€)', data: hist, tension:.35, borderWidth:2, pointRadius:0 }] },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      scales:{
        x:{ type:'time', time:{ unit:'day' }, grid:{ color:'#1f2730' }, ticks:{ color:'#9fb1c1' }},
        y:{ grid:{ color:'#1f2730' }, ticks:{ color:'#9fb1c1', callback:v=>v.toLocaleString('es-ES') } }
      },
      plugins:{
        legend:{ labels:{ color:'#cfe7df' } },
        tooltip:{ callbacks:{ label:(ctx)=> fmt(ctx.parsed.y) } }
      }
    }
  });

  // Rango (30D/90D/1A/TODO)
  document.querySelectorAll('[data-range]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      document.querySelectorAll('[data-range]').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const range = btn.dataset.range;
      const full = hist;
      let filtered = full;
      if(range!=='TODO'){
        const now = new Date(full.at(-1)?.x || Date.now());
        const from = new Date(now);
        if(range==='30D') from.setDate(now.getDate()-30);
        if(range==='90D') from.setDate(now.getDate()-90);
        if(range==='1A')  from.setFullYear(now.getFullYear()-1);
        filtered = full.filter(p => new Date(p.x) >= from);
      }
      lineChart.data.datasets[0].data = filtered;
      lineChart.update();
    });
  });

  // Distribución (donut)
  const dist = data.distribucion || data.distribution || [];
  const labels = dist.map(d=>d.ticker||d.name);
  const values = dist.map(d=>d.pct||d.valor||d.value);
  const ctx2 = document.getElementById('donutChart');
  const donut = new Chart(ctx2, {
    type:'doughnut',
    data:{ labels, datasets:[{ data: values }] },
    options:{
      plugins:{
        legend:{ display:false },
        tooltip:{ callbacks:{ label:(ctx)=> `${ctx.label}: ${ctx.raw.toFixed(2)}%` } }
      },
      cutout:'60%'
    }
  });
  // Leyenda simple
  document.getElementById('donutLegend').innerHTML = labels.map((l,i)=>`<span class="me-2"><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${donut.data.datasets[0].backgroundColor?.[i]||''};margin-right:6px;"></span>${l}</span>`).join('');

  // Alertas
  const alertas = data.alertas || [];
  const ul = document.getElementById('alertasList');
  if(!alertas.length){
    ul.innerHTML = `<li class="list-group-item bg-transparent text-secondary">Sin alertas.</li>`;
  }else{
    ul.innerHTML = alertas.slice(0,6).map(a=>`
      <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
        <div><i class="bi ${a.tipo==='warning'?'bi-exclamation-octagon text-warning':'bi-bell text-info'} me-2"></i>${a.texto}</div>
        <small class="text-secondary">${a.fecha}</small>
      </li>`).join('');
  }
})();
