const { DatabaseSync } = require('node:sqlite');
const { SerialPort } = require('serialport');
const { createServer } = require('node:http');
const { readFile, mkdirSync } = require('node:fs');
const path = require('node:path');
const { StringDecoder } = require('node:string_decoder');

const ROOT = path.resolve(__dirname, '..');
const ROSTER = {'A0:9B:19:5C': 'Finn Oostveen', 'B7:7A:FF:6D': 'Taynn Angel',
  'A1:E0:6B:9F': 'James de Beer', '29:41:E8:2A': 'Dylan van t woud'};
const LABELS = Object.values(ROSTER);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// 1. OPSLAAN: dezelfde database als de eerdere Python-versie.
class Store {
  constructor(filename) {
    mkdirSync(path.dirname(filename), {recursive: true});
    this.db = new DatabaseSync(filename);
    this.db.exec(`CREATE TABLE IF NOT EXISTS people (
      uid TEXT PRIMARY KEY, name TEXT NOT NULL, inside INTEGER, updated_at TEXT);
      CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY,
      uid TEXT NOT NULL, name TEXT NOT NULL, inside INTEGER NOT NULL, scanned_at TEXT NOT NULL);`);
    for (const [uid, name] of Object.entries(ROSTER)) {
      this.db.prepare('INSERT OR IGNORE INTO people(uid,name) VALUES (?,?)').run(uid, name);
    }
  }
  presence(uid, name, inside, event = false) {
    const stamp = new Date().toISOString();
    this.db.exec('BEGIN');
    try {
      this.db.prepare(`INSERT INTO people VALUES (?,?,?,?) ON CONFLICT(uid) DO UPDATE
        SET name=excluded.name, inside=excluded.inside, updated_at=excluded.updated_at`).run(uid, name, Number(inside), stamp);
      if (event) this.db.prepare('INSERT INTO scans(uid,name,inside,scanned_at) VALUES (?,?,?,?)').run(uid, name, Number(inside), stamp);
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  snapshot() {
    return {people: this.db.prepare('SELECT * FROM people ORDER BY name').all(),
      scans: this.db.prepare('SELECT * FROM scans ORDER BY id DESC LIMIT 100').all()};
  }
}

// De CPX stuurt een Python-woordenboek. Zet alleen tekst om; voer nooit code uit.
function readNames(text) {
  const json = text.replace(/'((?:\\.|[^'\\])*)'|"((?:\\.|[^"\\])*)"/g, (_, single, double) => {
    const value = single ?? double;
    const decoded = value.replace(/\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)/g, (_, escape) => {
      if (/^[ux]/.test(escape)) return String.fromCharCode(parseInt(escape.slice(1), 16));
      return ({n: '\n', r: '\r', t: '\t', '\\': '\\', "'": "'", '"': '"'})[escape] ?? '\\' + escape;
    });
    return JSON.stringify(decoded);
  });
  const names = JSON.parse(json);
  if (!names || Array.isArray(names) || typeof names !== 'object' || Object.values(names).some(name => typeof name !== 'string')) throw Error('Ongeldige taglijst');
  return names;
}

// 2. LEZEN: tagnummer + CHECKED IN/OUT worden samen één scan.
class Reader {
  constructor(store) {
    this.store = store;
    this.names = {...ROSTER};
    this.uid = null;
    this.mask = null;
    this.stopped = false;
    this.info = {connected: false, port: null, message: 'Reader zoeken…', last_line: ''};
  }
  parse(line) {
    this.info.last_line = line;
    if (line.startsWith('[STORAGE] Restored status bits:')) {
      this.mask = Number(line.split(':').at(-1));
      if (!Number.isInteger(this.mask) || this.mask < 0 || this.mask > 15) throw Error('Ongeldige status');
    } else if (line.startsWith('[STORAGE] Registered tags:')) {
      this.names = readNames(line.slice(line.indexOf(':') + 1));
      if (this.mask !== null) for (const [uid, name] of Object.entries(this.names)) {
        if (LABELS.includes(name)) this.store.presence(uid, name, Boolean(this.mask & (1 << LABELS.indexOf(name))));
      }
    } else if (line.startsWith('[SCAN] UID:')) {
      this.uid = line.slice(line.indexOf(':') + 1).trim();
    } else {
      const scan = line.match(/^(.+) - CHECKED (IN|OUT)$/);
      if (scan && this.uid && this.names[this.uid] === scan[1]) {
        this.store.presence(this.uid, scan[1], scan[2] === 'IN', true);
        this.info.message = 'Laatste scan: ' + scan[1];
        this.uid = null;
      }
    }
    if (line.startsWith('READY')) this.info.message = 'Reader gereed. Houd een tag tegen de scanner.';
    if (/^(\[ERROR\]|Traceback|MemoryError)/.test(line)) this.info.message = 'Reader meldt een fout: ' + line;
  }
  async connect() {
    let port = process.env.CPX_PORT;
    if (!port) {
      const ports = (await SerialPort.list()).filter(p => parseInt(p.vendorId, 16) === 0x239a);
      if (ports.length !== 1) throw Error('Sluit één CPX via USB aan. Meerdere readers? Stel CPX_PORT in.');
      port = ports[0].path;
    }
    this.usb = new SerialPort({path: port, baudRate: 115200, autoOpen: false});
    const usb = this.usb;
    let disconnected;
    const closed = new Promise(resolve => { disconnected = resolve; });
    usb.on('error', error => { this.info.message = error.message; disconnected(); });
    usb.on('close', disconnected);
    await new Promise((resolve, reject) => usb.open(error => error ? reject(error) : resolve()));
    Object.assign(this.info, {connected: true, port, message: 'Verbonden; reader starten…'});
    this.uid = this.mask = null;
    let pending = '';
    const decoder = new StringDecoder('utf8');
    usb.on('data', data => {
      pending += decoder.write(data);
      let end;
      while ((end = pending.indexOf('\n')) !== -1) {
        const line = pending.slice(0, end).replace(/\x1b\][^\x1b]*\x1b\\|\x1b\[[0-9;]*[A-Za-z]/g, '').trim();
        pending = pending.slice(end + 1);
        if (line) try { this.parse(line); } catch (error) { this.info.message = 'Onherkenbare readerregel: ' + line.slice(0, 160); }
      }
      if (pending.length > 8192) pending = '';
    });
    // Vraag de bewaarde CPX-status op. De CPX-code zelf blijft hetzelfde.
    const call = (method, ...args) => new Promise((resolve, reject) => usb[method](...args, error => error ? reject(error) : resolve()));
    try {
      await call('set', {dtr: true, rts: true});
      await wait(1000);
      await call('write', Buffer.from([3]));
      await wait(250);
      await call('flush');
      await call('write', Buffer.from([4]));
      await closed;
    } finally {
      if (usb.isOpen) await new Promise(resolve => usb.close(() => resolve()));
      this.info.connected = false;
    }
  }
  async run() {
    while (!this.stopped) {
      try { await this.connect(); }
      catch (error) { this.info.message = 'Geen readerverbinding. Sluit Serial in Mu en controleer USB. ' + error.message; }
      this.info.connected = false;
      if (!this.stopped) await wait(3000);
    }
  }
}

// 3. TONEN: HTML-bestanden en /api/attendance op dezelfde lokale server.
function serve({port = Number(process.env.PORT || 8080), database = path.join(__dirname, 'data/attendance.sqlite3'), readerEnabled = true} = {}) {
  const store = new Store(database);
  const reader = new Reader(store);
  const webroot = path.join(ROOT, 'Front-end');
  const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg'};
  const server = createServer((request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') { response.writeHead(405); return response.end(); }
    let pathname;
    try { pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname); }
    catch { response.writeHead(400); return response.end(); }
    if (pathname === '/api/attendance') {
      // Alleen de lokale Live Server mag deze gegevens vanaf een andere poort lezen.
      const origin = request.headers.origin;
      if (['http://127.0.0.1:5500', 'http://localhost:5500'].includes(origin)) {
        response.setHeader('Access-Control-Allow-Origin', origin);
      }
      response.setHeader('Vary', 'Origin');
      const body = JSON.stringify({...store.snapshot(), reader: reader.info});
      response.writeHead(200, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'});
      return response.end(request.method === 'HEAD' ? undefined : body);
    }
    const filename = path.resolve(webroot, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!filename.startsWith(webroot + path.sep)) { response.writeHead(403); return response.end(); }
    readFile(filename, (error, contents) => {
      if (error) { response.writeHead(404); return response.end('Niet gevonden'); }
      response.writeHead(200, {'Content-Type': (types[path.extname(filename)] || 'application/octet-stream') + (/\.(html|js|css)$/.test(filename) ? '; charset=utf-8' : ''), 'Cache-Control': 'no-cache'});
      response.end(request.method === 'HEAD' ? undefined : contents);
    });
  });
  server.on('error', error => { console.error('Server starten mislukt:', error.message); });
  server.listen(port, '127.0.0.1', () => {
    console.log(`Aanwezigheid: http://127.0.0.1:${server.address().port}/aanwezigheid.html`);
    if (readerEnabled) reader.run();
  });
  return {server, store, reader};
}

if (require.main === module) serve();
module.exports = {Store, Reader, readNames, serve, ROSTER};
