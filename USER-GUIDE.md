# Postural assessment — user guide

Tablet-based assessment recording, with automatic saving to the practice PC.

> English translation of `Mode_emploi.md`. The French version is the one
> shipped to the practice and is the reference for day-to-day use.

---

## 1. Every morning — start the server

On the **PC**, open the `C:\BilanPosturo` folder, then double-click
`demarrer-serveur.bat`.

A black window opens and shows:

```
Serveur HTTPS démarré.
  Sur ce PC  : https://localhost:8000
  Tablette   : https://192.168.1.13:8000
  Dépôt      : C:\Bilan_entrants
```

**Leave this window open all day.** Closing it stops the server: the tablet
will no longer be able to send assessments.

Minimising it to the taskbar is perfectly fine.

### If an error message appears

| Message | What to do |
|---|---|
| `Port 8000 indisponible` | The server is already running. Look for the other black window. |
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
- **Orange** — the assessment is on the tablet but **not** on the PC. Check
  that the black window is still open, then regenerate the PDF.
- **Red** — PDF creation failed. Nothing is lost: try again.

> **Never leave the page on an orange or red banner** without first checking
> that the assessment did arrive.

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
consultations for the week. A discrepancy points to an orange banner that went
unnoticed.

If an assessment is missing, check the tablet's Downloads: the local copy is
probably there and can be transferred to the PC by hand.

---

## Maintenance — for Baptiste

### The PC's address has changed

Symptom: the tablet shows a connection error or a security warning, although
nothing was changed.

```powershell
ipconfig | findstr IPv4
python generer_autorite.py <the_new_IP>
python serveur.py
```

The certificate authority is reused: **nothing to reinstall on the tablet**.
Remember to fix the home screen shortcut afterwards.

To stop this recurring, reserve the address as a static DHCP lease in the
router's interface (bind the Wi-Fi MAC address to `192.168.1.13`).

### Change the password

```powershell
python serveur.py --config
```

### The server certificate is expiring

Valid for 825 days. Regenerate it before the expiry date:

```powershell
python generer_autorite.py 192.168.1.13
```

The authority itself is valid for 10 years.

### Read the log

`C:\BilanPosturo\journal.log` keeps every request and every error. Search it
for `TLS refusé` or `Traceback` when something is unexplained.

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
