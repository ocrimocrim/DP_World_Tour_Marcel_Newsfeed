# Marcel Schneider Newsfeed Bot

Dieser Python-Bot ruft regelmäßig die News-Seite von Marcel Schneider auf,
archiviert alle gefundenen Artikel in einer SQLite-Datenbank und sendet neue
Meldungen in einen Discord-Channel via Webhook.

Die Zielseite setzt auf ein recht strenges Bot-Schutzsystem. Darum benutzt der
Scraper [cloudscraper](https://github.com/VeNoMouS/cloudscraper), um sich wie ein
vollwertiger Browser zu verhalten.

## Setup

1. (Optional) Virtuelle Umgebung erstellen.
2. Abhängigkeiten installieren:

   ```bash
   pip install -r requirements.txt
   ```

3. Einen Discord-Webhook für den Ziel-Channel anlegen und die URL bereithalten
   (z. B. `https://discordapp.com/api/webhooks/1428399222083948685/9VVpm1ob7BdsumnvXCIoXHA2TKWtgXEkcDab9bygNsx1fnzTeOxtKVMgpBWzllOjtBhO`).

4. Optional eine `.env`-Datei im Projektverzeichnis ablegen, damit der Bot den
   Webhook automatisch findet:

   ```env
   NEWSFEED_WEBHOOK_URL="https://discordapp.com/api/webhooks/1428399222083948685/9VVpm1ob7BdsumnvXCIoXHA2TKWtgXEkcDab9bygNsx1fnzTeOxtKVMgpBWzllOjtBhO"
   ```

   Alternativ kann die Variable direkt in der Shell gesetzt werden.

## Nutzung

* **Einmalige Ausführung zum Testen** – es wird nur archiviert und gesendet,
  wenn neue News gefunden wurden. Ohne gesetzte Umgebungsvariable muss die
  Webhook-URL explizit angegeben werden:

  ```bash
  python -m newsfeed --webhook-url "https://discord.com/api/webhooks/..." --once
  ```

* **Dauerbetrieb im Stunden-Takt** (Standardintervall 3600 Sekunden):

  ```bash
  python -m newsfeed --webhook-url "https://discord.com/api/webhooks/..."
  ```

  Der Intervall lässt sich mit `--interval` anpassen.

* **Archiv ausgeben**, um zu prüfen, was bereits erfasst wurde:

  ```bash
  python -m newsfeed --webhook-url dummy --dump-archive --limit 20
  ```

  `--limit` ist optional, ohne Limit werden alle Einträge ausgegeben.

Weitere nützliche Optionen:

* `--dry-run`: Archiviert neue News, sendet aber keine Discord-Benachrichtigung.
* `--database`: Pfad zur SQLite-Datei (Standard `news_archive.sqlite3`).
* `--ledger`: Pfad zu einer JSONL-Datei, die nach jedem Lauf das Archiv spiegelt
  (Standard `archive/news_archive.jsonl`). Leer lassen, um die Funktion zu
  deaktivieren.
* `--log-level`: Log-Level anpassen (z. B. `DEBUG`).

## Funktionsweise

1. **Scraper**: Ruft die Seite per `cloudscraper` ab und extrahiert die im
   Next.js-JSON (`__NEXT_DATA__`) enthaltenen News.
2. **Archiv**: Speichert jeden News-Eintrag (inkl. Original-Payload) in einer
   SQLite-Datenbank. Zusätzlich wird nach jedem Lauf eine JSONL-Datei im Ordner
   `archive/` aktualisiert, damit man die Historie direkt im Repo einsehen
   kann.
3. **Discord**: Neue Einträge werden in Form von Embeds an den gewünschten
   Webhook gesendet. Jede Nachricht enthält Titel, Link, Datum und ggf. die
   Kurzbeschreibung.
4. **Scheduler**: Der Bot kann entweder einmalig (`--once`) oder dauerhaft im
   angegebenen Intervall laufen.

## Automatischer Betrieb via GitHub Actions

Das Repository enthält unter `.github/workflows/newsfeed.yml` einen Workflow,
der den Bot stündlich über GitHub Actions startet (`cron: 0 * * * *`). Damit
die Benachrichtigungen funktionieren, muss im Repository ein Secret
`NEWSFEED_WEBHOOK_URL` mit der gewünschten Discord-Webhook-URL hinterlegt
werden. Der Workflow kann außerdem jederzeit manuell über den "Run workflow"-
Button gestartet werden.

## Hinweise

* Wenn die Seite den Bot trotzdem blockt, empfiehlt es sich, den Intervall zu
  vergrößern oder einen Proxy zu verwenden.
* Die Anwendung speichert das komplette Next.js-Datenpaket pro Abruf, sodass
  Debugging bei Formatänderungen einfacher wird.
* Für den produktiven Einsatz sollte der Bot als Dienst (z. B. systemd, Docker
  oder ein Cloud Scheduler) betrieben werden.
