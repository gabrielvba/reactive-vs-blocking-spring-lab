import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '30s', target: 5 },  // Acorda a API com 5 usuários
    { duration: '30s', target: 25 },  // 20 VUs é suficiente para popular o cache em 1 minuto
    { duration: '30s', target: 0 },  // Desliga suavemente
  ],
  thresholds: {
    // Mix inclui imagens até ~2.4MB; após redeploy a JVM está fria — p95 agressivo (sub-1s) falha sem indicar bug.
    // Objetivo: quase zero erros HTTP; latência só como rede de segurança larga para warmup.
    'http_req_duration{endpoint:base64}': ['p(95)<25000'],
    'http_req_duration{endpoint:raw}': ['p(95)<25000'],
    'errors': ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const ENDPOINT_TYPE = __ENV.ENDPOINT_TYPE || 'mixed';

// Distribuição de peso da vida real (80% das requisições são imagens pequenas, 20% imagens pesadas)
// Os arquivos originais do provider: '100kb', '395kb', '542kb', '1018kb', '2446kb', '6145kb', etc.
const WEIGHTED_IDS = [
  ...Array(40).fill('low-99kb'),
  ...Array(30).fill('low-394kb'),
  ...Array(20).fill('low-1018kb'),
  ...Array(10).fill('medium-2445kb'),
];

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
  sleep(0.2);
}

