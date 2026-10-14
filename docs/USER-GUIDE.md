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

Past 5 MB it is archived as `journal.log.1` and a new log starts; three
generations are kept. Calls to `/sante`, which arrive continuously from every
tablet that is switched on, are not recorded.

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
