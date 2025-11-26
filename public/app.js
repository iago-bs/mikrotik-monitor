// Frontend JS connects to backend SocketIO and updates Chart.js graph + metrics
const socket = io();

const ifaceSelect = document.getElementById('iface');
const currentIf = document.getElementById('current-if');
const cpuEl = document.getElementById('cpu');
const memEl = document.getElementById('mem');
const pingEl = document.getElementById('ping');
const pauseBtn = document.getElementById('pause');
const avgRxEl = document.getElementById('avg-rx');
const avgTxEl = document.getElementById('avg-tx');
const avgRxMbpsEl = document.getElementById('avg-rx-mbps');
const avgTxMbpsEl = document.getElementById('avg-tx-mbps');
const currentRxEl = document.getElementById('current-rx');
const currentTxEl = document.getElementById('current-tx');
const currentRxMbpsEl = document.getElementById('current-rx-mbps');
const currentTxMbpsEl = document.getElementById('current-tx-mbps');
const maxRxEl = document.getElementById('max-rx');
const maxTxEl = document.getElementById('max-tx');
const maxRxMbpsEl = document.getElementById('max-rx-mbps');
const maxTxMbpsEl = document.getElementById('max-tx-mbps');
const routerIpEl = document.getElementById('router-ip');
const connectionStatusEl = document.getElementById('connection-status');
const lastUpdateEl = document.getElementById('last-update');

let paused = false;
let maxRx = 0;
let maxTx = 0;
let isFirstReading = true;
let readingCount = 0;

pauseBtn.onclick = ()=> { paused = !paused; pauseBtn.textContent = paused ? 'Retomar' : 'Pausar'; };

async function loadInterfaces(){
  try{
    const res = await fetch('/api/interfaces');
    const data = await res.json();
    ifaceSelect.innerHTML = '<option value="">Selecione uma interface...</option>';
    data.forEach(i=>{
      const opt = document.createElement('option');
      opt.value = i.index;
      opt.text = i.name;
      ifaceSelect.appendChild(opt);
    });
    // Não seleciona automaticamente, deixa o usuário escolher
    console.log(`${data.length} interfaces carregadas`);
  }catch(e){
    console.error('Could not load interfaces', e);
  }
}
loadInterfaces();

ifaceSelect.onchange = ()=>{
  const idx = ifaceSelect.value;
  
  // Se selecionou a opção vazia, não faz nada
  if(!idx) return;
  
  const label = ifaceSelect.options[ifaceSelect.selectedIndex].text;
  currentIf.textContent = label;
  
  console.log(`Interface trocada para: ${label} (index: ${idx})`);
  
  // Limpar gráfico e máximos ao trocar de interface
  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[1].data = [];
  chart.update();
  maxRx = 0;
  maxTx = 0;
  maxRxEl.textContent = '0';
  maxTxEl.textContent = '0';
  maxRxMbpsEl.textContent = '0';
  maxTxMbpsEl.textContent = '0';
  
  // Reset flag de primeira leitura
  isFirstReading = true;
  readingCount = 0;
  
  socket.emit('select_iface', { iface: idx });
};

// Chart setup
const ctx = document.getElementById('bwChart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'line',
  data: { labels: [], datasets: [
    {label:'Rx (Kbps)', data: [], borderWidth:2, tension:0.25, borderColor:'blue', fill:false},
    {label:'Tx (Kbps)', data: [], borderWidth:2, tension:0.25, borderColor:'red', fill:false}
  ]},
  options: { 
    interaction:{mode:'index',intersect:false}, 
    plugins:{
      legend:{
        position:'top',
        labels: {
          generateLabels: function(chart) {
            const original = Chart.defaults.plugins.legend.labels.generateLabels;
            const labels = original.call(this, chart);
            // Adicionar valores atuais nas labels
            labels.forEach((label, i) => {
              const dataset = chart.data.datasets[i];
              const lastValue = dataset.data.length > 0 ? dataset.data[dataset.data.length - 1] : 0;
              label.text = `${label.text}: ${lastValue.toFixed(2)}`;
            });
            return labels;
          }
        }
      }
    }, 
    scales:{y:{title:{display:true,text:'Kbps'}}}
  }
});

socket.on('metrics', (m)=>{
  if(paused) return;
  
  // Se estava em erro, voltar para conectado ao receber métricas
  if(connectionStatusEl.className === 'status-error') {
    connectionStatusEl.textContent = 'Conectado';
    connectionStatusEl.className = 'status-connected';
  }
  
  // Filtro: ignorar valores absurdamente altos (provável erro inicial)
  const MAX_REASONABLE_KBPS = 1000000; // 1 Gbps
  if(m.rx_kbps > MAX_REASONABLE_KBPS || m.tx_kbps > MAX_REASONABLE_KBPS) {
    console.warn(`Valor anormal detectado e ignorado: Rx=${m.rx_kbps}, Tx=${m.tx_kbps}`);
    return;
  }
  
  const t = new Date(m.t).toLocaleTimeString();
  
  // Atualizar última atualização
  lastUpdateEl.textContent = t;
  
  chart.data.labels.push(t);
  chart.data.datasets[0].data.push(m.rx_kbps);
  chart.data.datasets[1].data.push(m.tx_kbps);
  if(chart.data.labels.length > 90){
    chart.data.labels.shift();
    chart.data.datasets.forEach(ds=>ds.data.shift());
  }
  
  // Atualizar labels da legenda com valores atuais
  chart.options.plugins.legend.labels.generateLabels = function(chart) {
    const datasets = chart.data.datasets;
    return datasets.map((dataset, i) => ({
      text: `${i === 0 ? 'Rx' : 'Tx'} (Kbps): ${m[i === 0 ? 'rx_kbps' : 'tx_kbps'].toFixed(2)}`,
      fillStyle: dataset.borderColor,
      strokeStyle: dataset.borderColor,
      lineWidth: dataset.borderWidth,
      hidden: !chart.isDatasetVisible(i),
      datasetIndex: i
    }));
  };
  
  chart.update('none');
  cpuEl.textContent = m.cpu_percent !== null ? m.cpu_percent : '-';
  memEl.textContent = m.mem_percent !== null ? m.mem_percent : '-';
  pingEl.textContent = m.latency_ms !== null ? m.latency_ms : '-';
  
  // Valores atuais
  currentRxEl.textContent = m.rx_kbps.toFixed(2);
  currentTxEl.textContent = m.tx_kbps.toFixed(2);
  currentRxMbpsEl.textContent = (m.rx_kbps / 1000).toFixed(2);
  currentTxMbpsEl.textContent = (m.tx_kbps / 1000).toFixed(2);
  
  // Atualizar máximos
  if(m.rx_kbps > maxRx) {
    maxRx = m.rx_kbps;
    maxRxEl.textContent = maxRx.toFixed(2);
    maxRxMbpsEl.textContent = (maxRx / 1000).toFixed(2);
  }
  if(m.tx_kbps > maxTx) {
    maxTx = m.tx_kbps;
    maxTxEl.textContent = maxTx.toFixed(2);
    maxTxMbpsEl.textContent = (maxTx / 1000).toFixed(2);
  }
  
  // Calcular médias
  const rxData = chart.data.datasets[0].data;
  const txData = chart.data.datasets[1].data;
  if(rxData.length > 0) {
    const avgRx = rxData.reduce((a,b)=>a+b,0) / rxData.length;
    const avgTx = txData.reduce((a,b)=>a+b,0) / txData.length;
    avgRxEl.textContent = avgRx.toFixed(2);
    avgTxEl.textContent = avgTx.toFixed(2);
    avgRxMbpsEl.textContent = (avgRx / 1000).toFixed(2);
    avgTxMbpsEl.textContent = (avgTx / 1000).toFixed(2);
  }
});

socket.on('connect', ()=> {
  console.log('connected to backend');
  connectionStatusEl.textContent = 'Conectado';
  connectionStatusEl.className = 'status-connected';
  
  // Buscar IP do router via API
  fetch('/api/config')
    .then(r => r.json())
    .then(data => {
      if(data.router_ip) routerIpEl.textContent = data.router_ip;
    })
    .catch(() => {});
});

socket.on('disconnect', ()=> {
  console.log('disconnected from backend');
  connectionStatusEl.textContent = 'Desconectado';
  connectionStatusEl.className = 'status-disconnected';
});

socket.on('error', (e)=> {
  console.error('backend error', e);
  connectionStatusEl.textContent = 'Erro';
  connectionStatusEl.className = 'status-error';
});
