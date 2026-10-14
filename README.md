# Postural Assessment

[![tests](https://github.com/baptiste5922/bilan-posturo/actions/workflows/tests.yml/badge.svg)](https://github.com/baptiste5922/bilan-posturo/actions/workflows/tests.yml)
[![licence: BUSL-1.1](https://img.shields.io/badge/licence-BUSL--1.1-orange.svg)](LICENSE)

Tablet application for recording postural assessments, with PDF generation and
automatic delivery to the practice workstation.

Built for a podiatry practice to replace paper forms: the practitioner fills in
the form on a tablet during the consultation, annotates the diagrams with a
stylus, and the assessment lands as a PDF on the practice computer with no
further handling.

Now used daily by the podiatrist for every postural assessment. PDF generation
produces structured reports that can be sent on directly, and saves time on
write-up.

**No data leaves the local network.** No cloud, no third-party service, no
account to create.

---

## How it works

```
    Tablet                          Practice PC
┌──────────────┐                 ┌──────────────────┐
│     Form     │                 │    serveur.py    │
│  + stylus    │ ──── HTTPS ───► │  (stdlib only)   │
│  → jsPDF     │   POST /depot   │        ↓         │
│  → queue     │ ◄─── GET ────── │ C:\Bilan_entrants│
│  (IndexedDB) │     /sante      │  (scheduled task)│
└──────────────┘                 └──────────────────┘
```

The PDF is produced **client-side** by html2canvas and jsPDF: the server only
receives an already-assembled file. It needs no Python dependency beyond the
standard library.

---

## Features

- Complete assessment form (history, examinations, orthotics)
- Stylus annotation over the skeletal diagrams and footprint charts, with a
  choice of colour and stroke width
- Multi-page PDF generation in the browser
- Automatic delivery to the practice workstation, falling back to a local
  download if the server is unreachable
- **Persistent delivery queue**: a generated assessment is stored in the
  browser before any upload and retried until the server acknowledges it, so a
  stopped server delays a delivery rather than losing one
- Automatic draft saving: a tablet that runs out of battery does not lose the
  work in progress
- Starts with the workstation as a scheduled task, with automatic restart
- HTTP Basic authentication over HTTPS
- Local copy to a desktop machine via the File System Access API

---

## Requirements

- Python 3.9 or later
- A PC and a tablet on the same local network
- `cryptography` — **only** to generate the certificates. The server itself
  runs on the standard library alone, so nothing extra has to be installed at
  the practice.

```bash
python -m pip install cryptography
```

---

## Setup

**1. Set the credentials**

```bash
python serveur/serveur.py --config
```

The password is hashed with PBKDF2-SHA256 (240,000 iterations, random salt)
and written to `config.json`. It is never stored in clear text.

**2. Generate the authority and the certificate**

```bash
python serveur/generer_autorite.py 192.168.1.13
```

Declare every address of the machine if it has several interfaces:

```bash
python serveur/generer_autorite.py 192.168.1.11 192.168.1.13
```

This produces a local certificate authority (`autorite.crt`, 10 years) and a
server certificate signed by it (825 days). The authority is reused from one
run to the next, so changing IP address requires no reinstallation on the
tablet.

**3. Install the authority on the devices**

Android — Settings → Security → Encryption & credentials → Install from
storage → **CA certificate** → `autorite.crt`

Windows — `Import-Certificate -FilePath autorite.crt -CertStoreLocation Cert:\CurrentUser\Root`

**4. Start**

```bash
python serveur/serveur.py
```

**5. Install the automatic start** (Windows, as administrator)

```powershell
.\installer-demarrage.ps1
```

Registers the `BilanPosturo` scheduled task — at system startup, as SYSTEM,
restarted up to five times — opens the firewall port, and prints the address
to use on the tablet. `.\desinstaller-demarrage.ps1` reverts to manual start.

Without this step the server depends on someone double-clicking
`demarrer-serveur.bat` every morning, and a workstation that rebooted
overnight greets the first patient with `ERR_CONNECTION_REFUSED`.

Because the task runs as SYSTEM, `dossier_pdf` must be an absolute local path
or a UNC path: a network drive mapped in the practitioner's session does not
exist for SYSTEM.

## Configuration

`config.json`, created by `--config`:

| Key | Purpose |
|---|---|
| `port` | Listening port (8000 by default) |
| `dossier_pdf` | Where assessments are written, absolute or relative to the project |
| `utilisateur` | HTTP Basic username |
| `mot_de_passe` | PBKDF2 digest, never the password itself |
| `certificat` / `cle_privee` | Paths to the TLS files |

---

## Security

The project handles health data. The following choices follow from that.

**Transport** — TLS 1.2 floor, ALPN advertised. The server refuses to start
without a valid certificate: no silent fallback to plain HTTP.

**Authentication** — HTTP Basic over TLS. The password is checked by
constant-time comparison over bytes. Both checks (username and password) always
run, with no short-circuit that would reveal through response timing whether
the username exists.

**Exposed surface** — two independent barriers. The web root is
`formulaire/`, which contains nothing but the form itself: `config.json`, the
private keys, `journal.log` and the Python source all live one level up and are
simply not inside the served tree. On top of that, only the extensions
`.html`, `.css`, `.js`, `.png`, `.jpg`, `.jpeg`, `.svg`, `.ico` are served, on
`GET` as well as on `HEAD`. Either barrier alone would be enough; a mistake in
one is caught by the other.

**File delivery** — sanitised filename (directory traversal neutralised,
Unicode normalisation, truncation), `%PDF-` signature verified, 30 MB ceiling,
write to a temporary file followed by an atomic rename. An interrupted transfer
never leaves a partial PDF behind. Existing names are suffixed rather than
overwritten.

**Health probe** — `GET /sante` answers `{"etat":"ok"}` without
authentication. It is the one unauthenticated route, and deliberately so: the
tablet uses it to tell a stopped server from a rejected password, which a 401
could not do. It discloses nothing beyond the open port, which already answers
401 to anyone who asks — no version, no paths, no counts — and is not written
to the log.

**Headers** — `X-Content-Type-Options: nosniff`, `Referrer-Policy:
no-referrer`, `Cache-Control: no-store`, `X-Frame-Options: DENY`.

### Known limitations

This system is designed for a trusted local network, on a single workstation.
It is not suitable for exposure to the internet: no rate limiting on attempts,
no encryption at rest for the delivered PDFs.

The delivery queue only makes progress while the form is open in the browser:
queued assessments survive a closed tab, but retries resume when the page is
loaded again. There is no service worker, and no background delivery.

Because the certificate authority is local, its private key
(`autorite-cle.pem`) must stay on the practice machine. Anyone holding it can
mint a certificate trusted by every device where `autorite.crt` is installed.

---

## Files that must never be committed

The bundled `.gitignore` excludes them:

```
config.json          password digest
*.pem                server and authority private keys
autorite.crt         local authority certificate
journal.log*         IP addresses, timestamps (and its rotated archives)
bilans/              health data
Bilan_entrants/
BilanPosturo-*.zip   distribution archives
node_modules/        build-time only; formulaire/lib/ is committed
__pycache__/  *.pyc
.DS_Store
```

`formulaire/lib/` holds the two vendored browser libraries and **is**
committed, so a fresh clone generates PDFs without any install step.

---

## Layout

```
bilan-posturo/
├── formulaire/             everything served to the tablet — the web root
│   ├── index.html
│   ├── script.js           PDF, stylus, draft, delivery
│   ├── style.css
│   ├── lib/                jspdf + html2canvas, committed
│   └── images/             skeletal diagrams, footprints, logo
├── serveur/
│   ├── serveur.py          HTTPS server and delivery endpoint
│   └── generer_autorite.py certificate authority + server certificate
├── docs/                   practitioner guides, French and English
├── outils/
│   ├── faire-paquet.sh     builds the archive to install at the practice
│   └── partager-paquet.sh  serves that archive over the local network
├── tests/                  Python for the server, Node for the delivery queue
├── demarrer-serveur.bat    manual Windows launcher, useful to see errors
├── installer-demarrage.ps1 registers the scheduled task and firewall rule
├── desinstaller-demarrage.ps1
└── config.json             not committed; created at the root at setup
```

Runtime state — `config.json`, `journal.log`, the certificates and `bilans/`
— lives at the project root, never inside `formulaire/`.


The code is in French, and so are the two documents the practice actually uses:
the software is deployed in a French practice and its sole user works in
French. `docs/USER-GUIDE.md` and `docs/READ-ME-FIRST.txt` are English translations
of those, kept alongside rather than in place of them.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ERR_EMPTY_RESPONSE` | TLS handshake failed, or an exception in a thread. Check `journal.log`, which records TLS rejections explicitly. |
| `ERR_SSL_PROTOCOL_ERROR` | An old process holds the port and answers in plain text. On Windows, `Get-NetTCPConnection -LocalPort 8000`. |
| `ERR_CERT_AUTHORITY_INVALID` | `autorite.crt` missing from the trust store, or the browser was not restarted. |
| `ERR_CERT_COMMON_NAME_INVALID` | The address being visited is not in the `subjectAltName`. Regenerate, declaring that address. |
| Port unavailable at startup | An instance is already running. |

`journal.log` records every request, every TLS negotiation failure and every
exception traceback.

---

## Technical notes

A few non-obvious points hit during development, written down here because they
recur in any TLS server built on the standard library.

**ALPN** — without `set_alpn_protocols`, Chrome closes the connection without
sending a single byte, where curl silently falls back to HTTP/1.1. The symptom
is an `ERR_EMPTY_RESPONSE` with no server-side trace at all.

**Invisible TLS errors** — when the listening socket is wrapped, negotiation
happens inside `get_request()`, and `socketserver` swallows the `OSError` there
without logging anything. `get_request` is overridden to surface them.

**`SO_REUSEADDR`** — the semantics differ by platform. On Windows it lets two
processes bind the same port, the old one still answering while the new one
reports a successful start. The flag is therefore conditioned on `os.name`.

**`hmac.compare_digest`** — raises `TypeError` on a string containing a
non-ASCII character. An accented username killed the thread and closed the
connection with no response. The comparison is done over UTF-8 bytes.

**Dual stack** — `localhost` resolves to `::1` first, so a server bound only to
`0.0.0.0` is unreachable there. Listening is done over IPv6 with `IPV6_V6ONLY`
disabled, falling back to IPv4 if the stack is absent.

---

## Licence

**Source-available, not open source.** The code is licensed under the
[Business Source License 1.1](https://mariadb.com/bsl11/) — see
[LICENSE](LICENSE), which is the only document that governs. Anyone can read,
audit, fork, and modify it; the restriction is on *production* use.

- **Reading, auditing, modifying and experimenting is free**, for anyone,
  with no grant needed. This is deliberate: a healthcare practice must be
  able to verify for itself that no patient data leaves the local network.
- **A healthcare practice may run the Licensed Work in production for the
  patients of its own practitioners** — see the `Additional Use Grant` in
  [LICENSE](LICENSE).
- **Providing the Licensed Work to third parties is not covered**: hosting it
  for others, distributing it, reselling it, embedding it in a commercial
  offering, or operating it on behalf of another practice all fall outside
  the grant.
- **Each version becomes MIT at most four years after its publication** — see
  `Change Date` in [LICENSE](LICENSE).
- **Everything up to and including commit `9339ee9`** (tag `frontiere-mit`,
  2026-10-14) **remains MIT forever** — a published grant cannot be
  withdrawn. That text is kept verbatim in
  [LICENSE-MIT-HISTORIQUE](LICENSE-MIT-HISTORIQUE).
- Running the software at a practice is also governed by a **separate
  subscription agreement**, which is not the licence: the licence settles
  what you may do with the code, the agreement settles the service.

Third-party components vendored under `formulaire/lib/` are attributed in
[TIERS.md](TIERS.md). French-language context for practitioners and auditors
is in [docs/licence.md](docs/licence.md).
