/**
 * ==========================================================================
 * 해외선교 총괄 관제 포털 - 초경량 독립 백엔드 서버 (Node.js Native Server)
 * - 외부 npm 패키지 설치 없이 Node.js만으로 즉시 구동 (Zero Dependencies)
 * - 정적 파일 서빙 (HTML, CSS, JS, 이미지)
 * - REST API (지경 데이터, 인재 데이터, 세션)
 * ==========================================================================
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 3000;
const ROOT_DIR = __dirname;
const DB_FILE = path.join(ROOT_DIR, 'data_store.json');

// MIME 타입 매핑
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf'
};

// 초기 서버 상태 (data_store.json이 있으면 로드, 없으면 기본값)
function loadDatabase() {
  if (fs.existsSync(DB_FILE)) {
    try {
      const content = fs.readFileSync(DB_FILE, 'utf-8');
      return JSON.parse(content);
    } catch (e) {
      console.error('[DB] 로드 오류, 기본 메모리 상태로 시작합니다:', e.message);
    }
  }
  return {
    customTerritories: [],
    customTalents: [],
    logs: []
  };
}

function saveDatabase(data) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (e) {
    console.error('[DB] 저장 오류:', e.message);
  }
}

let db = loadDatabase();

// HTTP 서버 생성
const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = decodeURIComponent(parsedUrl.pathname);

  // CORS 헤더 설정 (외부 통신 허용)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // ==========================================================================
  // [REST API 라우트]
  // ==========================================================================
  
  // 1. 서버 헬스체크
  if (pathname === '/api/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ status: 'ok', serverTime: new Date().toISOString() }));
    return;
  }

  // 2. 신규 지경 데이터 추가 API
  if (pathname === '/api/territories' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const newTerritory = JSON.parse(body);
        db.customTerritories.unshift(newTerritory);
        saveDatabase(db);
        res.writeHead(201, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: true, item: newTerritory }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: false, error: '잘못된 요청 형식입니다.' }));
      }
    });
    return;
  }

  // 2-1. 지경 데이터 수정 API
  if (pathname.startsWith('/api/territories/') && req.method === 'PUT') {
    const id = pathname.replace('/api/territories/', '');
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const updated = JSON.parse(body);
        const idx = db.customTerritories.findIndex(t => t.id === id);
        if (idx !== -1) {
          db.customTerritories[idx] = updated;
        } else {
          db.customTerritories.unshift(updated);
        }
        saveDatabase(db);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: true, item: updated }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: false, error: '잘못된 요청 형식입니다.' }));
      }
    });
    return;
  }

  // 2-2. 지경 데이터 삭제 API
  if (pathname.startsWith('/api/territories/') && req.method === 'DELETE') {
    const id = pathname.replace('/api/territories/', '');
    db.customTerritories = db.customTerritories.filter(t => t.id !== id);
    saveDatabase(db);
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ success: true, id }));
    return;
  }

  // 3. 신규 인재 데이터 추가 API
  if (pathname === '/api/talents' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const newTalent = JSON.parse(body);
        db.customTalents.unshift(newTalent);
        saveDatabase(db);
        res.writeHead(201, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: true, item: newTalent }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: false, error: '잘못된 요청 형식입니다.' }));
      }
    });
    return;
  }

  // 3-1. 인재 데이터 수정 API
  if (pathname.startsWith('/api/talents/') && req.method === 'PUT') {
    const id = pathname.replace('/api/talents/', '');
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const updated = JSON.parse(body);
        const idx = db.customTalents.findIndex(t => t.id === id);
        if (idx !== -1) {
          db.customTalents[idx] = updated;
        } else {
          db.customTalents.unshift(updated);
        }
        saveDatabase(db);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: true, item: updated }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: false, error: '잘못된 요청 형식입니다.' }));
      }
    });
    return;
  }

  // 3-2. 인재 데이터 삭제 API
  if (pathname.startsWith('/api/talents/') && req.method === 'DELETE') {
    const id = pathname.replace('/api/talents/', '');
    db.customTalents = db.customTalents.filter(t => t.id !== id);
    saveDatabase(db);
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ success: true, id }));
    return;
  }

  // 4. 저장된 지경 및 인재 조회 API
  if (pathname === '/api/data' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({
      customTerritories: db.customTerritories,
      customTalents: db.customTalents
    }));
    return;
  }

  // ==========================================================================
  // [정적 웹 파일 서빙 (Frontend Delivery)]
  // ==========================================================================
  let filePath = path.join(ROOT_DIR, pathname === '/' ? 'index.html' : pathname);

  // 상위 경로 탈출 공격 방지
  if (!filePath.startsWith(ROOT_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('접근 권한이 없습니다.');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(`
        <div style="font-family: sans-serif; text-align: center; padding: 5rem 1rem;">
          <h2>404 - 파일을 찾을 수 없습니다</h2>
          <p style="color: #64748b;">요청하신 페이지가 서버에 존재하지 않습니다: ${pathname}</p>
          <a href="/" style="color: #86cab6; font-weight: bold;">메인 포털로 돌아가기</a>
        </div>
      `);
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    res.writeHead(200, { 'Content-Type': contentType });
    const readStream = fs.createReadStream(filePath);
    readStream.pipe(res);
  });
});

server.listen(PORT, () => {
  console.log('================================================================');
  console.log('  🌐 [해외선교 총괄 관제 포털] 서버가 성공적으로 시작되었습니다.');
  console.log('================================================================');
  console.log(`  👉 로컬 접속 주소 : http://localhost:${PORT}`);
  console.log(`  🔒 권한 대상       : 중앙 부장 · 총무 · 서무 전용`);
  console.log('  💡 종료하려면 터미널에서 Ctrl + C 를 누르세요.');
  console.log('================================================================');
});
