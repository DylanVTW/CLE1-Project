// Live Server toont de pagina op 5500; de readerkoppeling draait op 8080.
const liveServer = location.port === '5500' && ['127.0.0.1', 'localhost'].includes(location.hostname);
const api = liveServer ? 'http://127.0.0.1:8080/api/attendance' : '/api/attendance';

// 1. Maak een tabelregel. textContent houdt namen veilig als gewone tekst.
function addRow(table, values) {
  const row = table.insertRow();
  for (const value of values) row.insertCell().textContent = value;
}

function date(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('nl-NL', {timeZone: 'Europe/Amsterdam'});
}

function status(inside, action = false) {
  if (inside === null) return 'Onbekend';
  if (inside) return action ? 'Ingecheckt' : 'Aanwezig';
  return action ? 'Uitgecheckt' : 'Afwezig';
}

// 2. Vul de website met de ontvangen personen en scans.
function show(data) {
  document.getElementById('connection-dot').classList.toggle('online', data.reader.connected);
  document.getElementById('connection-title').textContent = data.reader.connected ? 'Reader verbonden' : 'Reader niet verbonden';
  document.getElementById('connection-message').textContent = data.reader.message;
  document.getElementById('reader-log').textContent = data.reader.last_line || 'Nog geen uitvoer ontvangen.';
  const people = document.getElementById('people');
  const scans = document.getElementById('scans');
  people.replaceChildren();
  scans.replaceChildren();
  for (const person of data.people) {
    addRow(people, [person.name, status(person.inside), date(person.updated_at)]);
    const cell = people.lastChild.cells[1];
    cell.className = person.inside === null ? 'unknown' : person.inside ? 'in' : 'out';
  }
  for (const scan of data.scans) {
    addRow(scans, [date(scan.scanned_at), scan.name, status(scan.inside, true)]);
    scans.lastChild.cells[2].className = scan.inside ? 'in' : 'out';
  }
  if (!data.scans.length) addRow(scans, ['Nog geen scans ontvangen.', '', '']);
  document.getElementById('count-in').textContent = data.people.filter(p => p.inside === 1).length;
  document.getElementById('count-out').textContent = data.people.filter(p => p.inside === 0).length;
  document.getElementById('count-unknown').textContent = data.people.filter(p => p.inside === null).length;
  document.getElementById('refresh-time').textContent = 'Laatst opgehaald: ' + date(new Date());
}

// 3. Vraag nieuwe gegevens op. Wacht daarna één seconde en herhaal.
async function refresh() {
  try {
    const response = await fetch(api, {cache: 'no-store', signal: AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error('Geen gegevens');
    show(await response.json());
  } catch (error) {
    document.getElementById('connection-dot').classList.remove('online');
    document.getElementById('connection-title').textContent = 'Websitekoppeling niet bereikbaar';
    document.getElementById('connection-message').textContent = 'Start de aanwezigheidsserver met Start-aanwezigheid.cmd. Eerder getoonde gegevens kunnen verouderd zijn.';
    document.getElementById('refresh-time').textContent = 'Geen actuele verbinding — getoonde gegevens kunnen verouderd zijn.';
  } finally {
    setTimeout(refresh, 1000);
  }
}
refresh();
