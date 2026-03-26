import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const timeoutErrors = new Counter('timeout_errors');  // Contador de timeouts
const connectionErrors = new Counter('connection_errors');  // Erros de conexão
const serverErrors = new Counter('server_errors');  // Erros 5xx
const clientErrors = new Counter('client_errors');  // Erros 4xx

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Prepara o ambiente
    { duration: '1m', target: 150 },   // Onde o Base64 começa a quebrar (OOM / limite de Heap)
    { duration: '1m', target: 300 },   // Onde o Raw começa a enfileirar muito (Limite de Thread Pool)
    { duration: '2m', target: 400 },   // Ponto de saturação absoluta
    { duration: '30s', target: 50 },    // Resfriamento
  ],
  thresholds: {
    // Stress até 400 VUs: o sinal principal é taxa de falha/timeout; p95 rígido faz o k6 sair com erro
    // mesmo com 0% http_req_failed (saturação = latência alta, não necessariamente erro HTTP).
    http_req_failed: ['rate<0.05'],
    'http_req_duration{endpoint:base64}': ['p(95)<60000'],
    'http_req_duration{endpoint:raw}': ['p(95)<60000'],
    timeout_errors: ['count<100'],
    connection_errors: ['count<30'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// Configuração de Pesos
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
    [`status is 2xx on ${endpoint}`]: (r) => r.status >= 200 && r.status < 300,
  });

  // Contabilizar erros gerais
  errorRate.add(!success, { endpoint });

  // Contabilizar tipos específicos de erro
  if (!success) {
    // Verificar se é timeout
    if (res.error && (res.error.includes('timeout') || res.error.includes('i/o timeout'))) {
      timeoutErrors.add(1, { endpoint, image_size: id });
      console.warn(`TIMEOUT on ${endpoint}/${id}: ${res.error}`);
    }
    // Verificar se é erro de conexão
    else if (res.error && (res.error.includes('connection') || res.error.includes('dial') || res.error.includes('refused'))) {
      connectionErrors.add(1, { endpoint, image_size: id });
      console.warn(`CONNECTION ERROR on ${endpoint}/${id}: ${res.error}`);
    }
    // Verificar se é erro 5xx (servidor)
    else if (res.status >= 500 && res.status < 600) {
      serverErrors.add(1, { endpoint, status_code: res.status, image_size: id });
      console.warn(`SERVER ERROR ${res.status} on ${endpoint}/${id}`);
    }
    // Verificar se é erro 4xx (cliente)
    else if (res.status >= 400 && res.status < 500) {
      clientErrors.add(1, { endpoint, status_code: res.status, image_size: id });
      console.warn(`CLIENT ERROR ${res.status} on ${endpoint}/${id}`);
    }
  }

  sleep(0.1);
}
