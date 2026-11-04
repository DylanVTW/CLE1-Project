// Live Server toont de pagina op 5500; de readerkoppeling draait op 8080.
const liveServer = location.port === '5500' && ['127.0.0.1', 'localhost'].includes(location.hostname);
const api = liveServer ? 'http://127.0.0.1:8080/api/attendance' : '/api/attendance';

function maakVak(lijst, teksten) {
  const vak = document.createElement('div');
  vak.className = 'gegevens-vak';
  for (const tekst of teksten) {
    const alinea = document.createElement('p');
    alinea.textContent = tekst;
    vak.appendChild(alinea);
  }
  lijst.appendChild(vak);
  return vak;
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
  document.getElementById('verbinding-lampje').classList.toggle('verbonden', data.reader.connected);
  document.getElementById('verbinding-titel').textContent = data.reader.connected ? 'Reader verbonden' : 'Reader niet verbonden';
  document.getElementById('verbinding-tekst').textContent = data.reader.message;
  document.getElementById('scanner-bericht').textContent = data.reader.last_line || 'Nog geen uitvoer ontvangen.';
  const people = document.getElementById('personenlijst');
  const scans = document.getElementById('scanlijst');
  people.replaceChildren();
  scans.replaceChildren();
  for (const person of data.people) {
    const vak = maakVak(people, [
      'Naam: ' + person.name,
      'Status: ' + status(person.inside),
      'Laatst bijgewerkt: ' + date(person.updated_at)
    ]);
    vak.children[1].className = person.inside === null ? 'onbekend' : person.inside ? 'aanwezig' : 'afwezig';
  }
  for (const scan of data.scans) {
    const vak = maakVak(scans, [
      'Tijdstip: ' + date(scan.scanned_at),
      'Naam: ' + scan.name,
      'Actie: ' + status(scan.inside, true)
    ]);
    vak.children[2].className = scan.inside ? 'aanwezig' : 'afwezig';
  }
  if (!data.scans.length) maakVak(scans, ['Nog geen scans ontvangen.']);
  document.getElementById('aantal-aanwezig').textContent = data.people.filter(p => p.inside === 1).length;
  document.getElementById('aantal-afwezig').textContent = data.people.filter(p => p.inside === 0).length;
  document.getElementById('aantal-onbekend').textContent = data.people.filter(p => p.inside === null).length;
  document.getElementById('bijgewerkt-op').textContent = 'Laatst opgehaald: ' + date(new Date());
}

// 3. Vraag nieuwe gegevens op. Wacht daarna één seconde en herhaal.
async function refresh() {
  try {
    const response = await fetch(api, {cache: 'no-store', signal: AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error('Geen gegevens');
    show(await response.json());
  } catch (error) {
    document.getElementById('verbinding-lampje').classList.remove('verbonden');
    document.getElementById('verbinding-titel').textContent = 'Websitekoppeling niet bereikbaar';
    document.getElementById('verbinding-tekst').textContent = 'Start de aanwezigheidsserver met Start-aanwezigheid.cmd. Eerder getoonde gegevens kunnen verouderd zijn.';
    document.getElementById('bijgewerkt-op').textContent = 'Geen actuele verbinding — getoonde gegevens kunnen verouderd zijn.';
  } finally {
    setTimeout(refresh, 1000);
  }
}
refresh();
