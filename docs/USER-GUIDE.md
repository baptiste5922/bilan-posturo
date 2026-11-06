# Postural assessment — user guide

Tablet-based assessment recording, with automatic saving to the practice PC.

> English translation of `Mode_emploi.md`. The French version is the one
> shipped to the practice and is the reference for day-to-day use.

---

## 1. Every morning — nothing to do

The server starts with the PC and restarts itself if it stops. No window to
open, nothing to leave running.

### Checking that it answers

From the tablet or from the PC, open:

```
https://192.168.1.13:8000/sante
```

`{"etat":"ok"}` means the server is running. This is the only check worth
making: it answers without credentials.

### Restarting it by hand

If the tablet cannot connect, on the PC, in PowerShell:

```powershell
Start-ScheduledTask -TaskName BilanPosturo
```

To see an error message, double-click `demarrer-serveur.bat` instead: the
server then runs in a visible window.

| Message | What to do |
|---|---|
| `Port 8000 indisponible` | The server is already running; nothing to do. |
| `certificat.pem introuvable` | See the Maintenance section. |
| `config.json absent` | See the Maintenance section. |

---

## 2. During the consultation — fill in the assessment

On the **tablet**, tap the **Bilan posturo** shortcut on the home screen.

On the first launch of the day, the tablet asks for a username and password:
these are the practice credentials, entered once per session.

Fill in the form. Stylus annotations on the skeletal diagrams and the
footprints are saved into the final PDF.

> **The draft is saved automatically.** If the tablet shuts down or Chrome
> closes, the entry is offered for recovery at the next launch.

> **If the form does not display, or a red message says so,** tap the
> **"Formulaire — secours V1"** bookmark — or, if it is gone, add
> `index-v1.html` to the end of the usual address. It is the same form, the
> same draft, the same delivery; the entry in progress is kept.

---

## 3. At the end of the consultation — generate the assessment

Tap the PDF generation button at the bottom of the form. Two things happen:

1. The PDF is sent to the PC and lands in `C:\Bilan_entrants`
2. A copy is downloaded onto the tablet

A coloured banner confirms the outcome:

- **Green** — the assessment reached the PC. All good.
- **Orange** — the practice server was not answering. The assessment is held
  on the tablet and **will be sent on its own** as soon as the server answers.
  Nothing to redo, and above all do not regenerate the PDF.
- **Red** — PDF creation failed, or the PC rejected the file. Nothing is lost:
  try again.

While assessments are waiting, a banner stays at the top of the page with the
count. **Réessayer maintenant** forces an attempt straight away.

> **What keeps the queue moving is an open page.** Queued assessments are held
> in the tablet and survive Chrome closing, but delivery only resumes when the
> form is loaded again. At the end of the day, leave the page open until the
> banner disappears.

---

## 4. At the end of the day — file the assessments

This is the step not to forget. It takes two minutes.

### On the PC

Open `C:\Bilan_entrants`: the day's assessments are there, named
`Bilan_2026-08-22_Dupont-Lea.pdf`.

Move them to their permanent filing location (by patient, by year — whatever
the practice uses). `C:\Bilan_entrants` should be **empty** at the end of the
day: that is what makes it obvious at a glance what is still to be filed.

### On the tablet

The downloaded copies pile up in **Downloads**. They duplicate the ones on the
PC.

Open the **Files** app → **Downloads**, select the PDFs starting with
`Bilan_`, and delete them.

> **Why delete them?** These copies contain health data. A tablet is more
> easily lost or stolen than a desktop PC: the less it holds, the better. The
> reference copy is the one on the PC.

To be done at least once a week.

---

## 5. Weekly check

On Friday, check that the number of filed assessments matches the number of
consultations for the week.

A discrepancy can no longer come from a missed delivery: an assessment the
server never received stays queued on the tablet and shows in the waiting
banner. Opening the form is enough to resume delivery.

If an assessment is missing all the same, the local copy is in the tablet's
Downloads and can be transferred by hand.

---

## Maintenance — for Baptiste

### Automatic start

Installed once, as administrator:

```powershell
.\installer-demarrage.ps1
```

It registers the `BilanPosturo` scheduled task (at system startup, as SYSTEM,
restarted up to five times) and the firewall rule.
`.\desinstaller-demarrage.ps1` reverts to manual start.

Before a remote installation, run the check-only mode first: it verifies the
script's location, `config.json` and `pythonw.exe`, then stops before the
scheduled task and the firewall rule, changing nothing.

```powershell
.\installer-demarrage.ps1 -Verifier   # check only, changes nothing
```

```powershell
Get-ScheduledTask -TaskName BilanPosturo          # state
Get-ScheduledTaskInfo -TaskName BilanPosturo      # last result, last run
Stop-ScheduledTask  -TaskName BilanPosturo        # stop
Start-ScheduledTask -TaskName BilanPosturo        # restart
```

The task runs under `pythonw.exe`, without a console: everything the server
has to say goes to `journal.log`. After editing `config.json` or the
certificate, stop and restart the task.

A consequence of the SYSTEM account: `dossier_pdf` must be an absolute local
path or a UNC path. A network drive mapped in the practitioner's session does
not exist for SYSTEM.

### The PC's address has changed

Symptom: the tablet shows `ERR_CONNECTION_TIMED_OUT` or a security warning,
although nothing was changed. `ERR_CONNECTION_REFUSED` means the opposite: the
PC is reachable and the server is not running on it — look at the scheduled
task, not at the address.

```powershell
ipconfig | findstr IPv4
python serveur/generer_autorite.py <the_new_IP>
python serveur/serveur.py
```

The certificate authority is reused: **nothing to reinstall on the tablet**.
Remember to fix the home screen shortcut afterwards.

To stop this recurring, reserve the address as a static DHCP lease in the
router's interface (bind the Wi-Fi MAC address to `192.168.1.13`).

### Change the password

```powershell
python serveur/serveur.py --config
```

### The server certificate is expiring

Valid for 825 days. Regenerate it before the expiry date:

```powershell
python serveur/generer_autorite.py 192.168.1.13
```

The authority itself is valid for 10 years.

### Read the log

`C:\BilanPosturo\journal.log` keeps every request and every error. Search it
for `TLS refusé` or `Traceback` when something is unexplained.

It is archived as `journal.log.1` and a new log starts as soon as it passes
5 MB, **or** as soon as its first line is more than one month (30 days) old.
Older archives shift up (`.2`, `.3`, ...) and **no line is kept for more than
six months**: an archive is deleted as soon as its first line is more than six
months (180 days) minus one day old. The check runs when the server starts,
each time a new archive is made, when the log is written (at most once a day)
and, while the server runs, every six hours even if nothing is written any
more. A stopped server purges nothing until it next starts. At most seven
generations of archives exist at once in normal operation. Deletion is
permanent, and it happens archive by archive: a recent line can therefore
disappear up to a month before its six months, if it shares its archive with an
older line. **Exception, the first time:** at the first start after the update,
the whole earlier history becomes a single archive, which goes in one piece
when its first line reaches the limit. The most recent lines of that archive
can then go up to several months before their six months. Calls to `/sante`,
which arrive continuously from every tablet that is switched on, are not
recorded.

The duration is set in `config.json` with the `"conservation_journaux_mois"`
line (an integer from 1 to 120, **6 by default**); an invalid value is ignored
and replaced by 6. It applies to both logs. Restart the server after changing
it.

### The second log, the one that can be sent

A second file, `C:\BilanPosturo\technique.log`, lives next to the first one.
It notes startups, shutdowns and technical incidents (certificate,
authentication, deliveries), but **never an address, never a file name, never
anything that belongs to a patient**. That is the difference between the two:
`journal.log` must never leave the practice; `technique.log` can, by email, to
support, for a remote diagnosis without any health data leaving the PC.

It rotates and is purged exactly like the other log: archived past 5 MB or one
month, and no line kept beyond six months (`"conservation_journaux_mois"`, see
above). A single duration applies to both files.

To switch it off (there should be no reason to, but the fallback exists): open
`config.json` at the root, add or set the `"journal_technique"` line to
`false`, save, restart the server. The file already written can stay as is;
it simply stops being fed.

### The status page

A read-only diagnostic page, to name an incident within a minute during a
support session. On the practice PC, in a browser: `https://localhost:8000/etat`
(replace `8000` with the port in `config.json`), with the usual username and
password. Without them the page answers "unauthorised" like everything else:
only the health probe `/sante` is open to everyone.

It tells, line by line:

- **Version** — the same as the form footer and `technique.log`;
- **Server started on** — the date of the last start (the `ARRET` log line is
  almost never written: this date replaces it);
- **Last assessment received** — "none since startup" until one arrives; the
  value is lost at every restart;
- **Free space** on the disk that holds the PDF folder;
- **Certificate valid until** — with the days left, and the mention "to be
  renewed" under 30 days (see "The server certificate is expiring");
- **Certificate fingerprint** — the same as the `DEMARRAGE` lines of
  `technique.log`;
- **PC address and certificate** — `conforme` (the certificate covers an
  address the PC carries), `adresse changée` (it covers none any more: follow
  "The PC's address has changed" above) or `indéterminé` (the certificate only
  carries `localhost`, nothing to compare);
- **Practice identity** — "not filled in" means assessment export is refused:
  run `python serveur/serveur.py --config`;
- the **last 30 lines of `technique.log`**.

Nothing it shows identifies a patient, a file or an address: it can be
photographed or pasted into an email, like `technique.log`. It writes nothing
and triggers nothing.

To read it from a program, request it with the header
`Accept: application/json`.

To switch it off: in `config.json`, add or set the `"page_etat"` line to
`false`, then stop and restart the scheduled task. `/etat` then answers as it
did before it existed ("unauthorised" without credentials, "file type not
served" with them).

### Files that must never be shared

- `autorite-cle.pem` — allows forging trusted certificates
- `cle.pem` — the server key
- `config.json` — holds the password digest

To be excluded from any Git repository.

---

## Quick reference

| | |
|---|---|
| Tablet address | `https://192.168.1.13:8000` |
| Assessments arrive in | `C:\Bilan_entrants` |
| Project folder | `C:\BilanPosturo` |
| Start | `demarrer-serveur.bat` |
| Fallback | *Formulaire — secours V1* bookmark, or `index-v1.html` |
