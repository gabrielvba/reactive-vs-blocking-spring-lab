import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const timeoutErrors = new Counter('timeout_errors');
const connectionErrors = new Counter('connection_errors');
const serverErrors = new Counter('server_errors');
const clientErrors = new Counter('client_errors');

export const options = {
  stages: [
    { duration: '30s', target: 25 },   // Rampa inicial suave
    { duration: '1m', target: 50 },    // Sobe até 50 VUs (tráfego estável normal)
    { duration: '1m', target: 100 },   // Pico de carga (Limite teórico seguro para Base64 sob 768MB RAM)
    { duration: '2m', target: 100 },   // Voo de cruzeiro por 2m para medir a estabilidade sustentada
    { duration: '30s', target: 0 },    // Rampa de descida
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
    'http_req_duration{endpoint:base64}': ['p(95)<1000'],
    'http_req_duration{endpoint:raw}': ['p(95)<800'],
    errors: ['rate<0.05'],
    timeout_errors: ['count<10'],
    connection_errors: ['count<5'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// Configuração de Pesos para o Load Test:
// Na vida real, poucos usuários puxam imagens gigantes ao mesmo tempo.
// Se todos puxarem arquivos de 2MB ao mesmo tempo, a API estoira o limite de memória instantaneamente.
const WEIGHTED_IDS = [
  ...Array(50).fill('low-99kb'),
  ...Array(30).fill('low-394kb'),
  ...Array(15).fill('low-1018kb'),
  ...Array(5).fill('medium-2445kb'),
];

const ENDPOINT_TYPE = __ENV.ENDPOINT_TYPE || 'mixed';

function getEndpoint() {
  if (ENDPOINT_TYPE === 'base64') return 'base64';
  if (ENDPOINT_TYPE === 'raw') return 'raw';
  return Math.random() < 0.5 ? 'base64' : 'raw';
}

export default function () {
  const id = WEIGHTED_IDS[Math.floor(Math.random() * WEIGHTED_IDS.length)];
  const endpoint = getEndpoint();
  const url = `${BASE_URL}/file/${endpoint}/${id}`;

  const res = http.get(url, { tags: { endpoint } });

  const success = check(res, {
    [`status 200 on ${endpoint}`]: (r) => r.status === 200,
  });

  errorRate.add(!success, { endpoint });

  // Contabilizar tipos específicos de erro
  if (!success) {
    if (res.error && (res.error.includes('timeout') || res.error.includes('i/o timeout'))) {
      timeoutErrors.add(1, { endpoint, image_size: id });
      console.warn(`TIMEOUT on ${endpoint}/${id}: ${res.error}`);
    }
    else if (res.error && (res.error.includes('connection') || res.error.includes('dial') || res.error.includes('refused'))) {
      connectionErrors.add(1, { endpoint, image_size: id });
      console.warn(`CONNECTION ERROR on ${endpoint}/${id}: ${res.error}`);
    }
    else if (res.status >= 500 && res.status < 600) {
      serverErrors.add(1, { endpoint, status_code: res.status, image_size: id });
      console.warn(`SERVER ERROR ${res.status} on ${endpoint}/${id}`);
    }
    else if (res.status >= 400 && res.status < 500) {
      clientErrors.add(1, { endpoint, status_code: res.status, image_size: id });
      console.warn(`CLIENT ERROR ${res.status} on ${endpoint}/${id}`);
    }
  }

  sleep(Math.random() * 0.3);
}

