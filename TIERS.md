# Composants tiers

`bilan-posturo` est publié sous [Business Source License 1.1](LICENSE), mais
embarque deux bibliothèques JavaScript tierces, vendorisées dans
`formulaire/lib/` et versionnées telles quelles. Les deux sont sous licence
**MIT**, dont le texte figure une fois ci-dessous — leur licence propre n'est
pas affectée par celle du dépôt.

## jsPDF

- **Version :** 4.2.1
- **Fichier :** `formulaire/lib/jspdf.umd.min.js`
- **Titulaire du droit d'auteur :** James Hall et les contributeurs du projet
  jsPDF (voir le bandeau `/** @license` en tête du fichier)
- **Licence :** MIT
- **Site :** <https://github.com/parallax/jsPDF>

## html2canvas

- **Version :** 1.4.1
- **Fichier :** `formulaire/lib/html2canvas.min.js`
- **Titulaire du droit d'auteur :** Niklas von Hertzen (voir le bandeau `/*!`
  en tête du fichier)
- **Licence :** MIT
- **Site :** <https://github.com/niklasvh/html2canvas>

Les bandeaux de licence déjà présents en tête de chacun des deux fichiers ne
sont pas retirés : ils sont la preuve que l'attribution voyage avec le code,
y compris dans l'archive livrée au cabinet.

## Texte de la licence MIT (jsPDF et html2canvas)

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## RFC 8032 — Ed25519

- **Fichier :** `serveur/signature_ed25519.py` (vérification seule)
- **Origine :** RFC 8032, *Edwards-Curve Digital Signature Algorithm (EdDSA)*,
  S. Josefsson et I. Liusvaara, janvier 2017 — §5.1.3 (décodage d'un point) et
  §5.1.7 (vérification) — <https://www.rfc-editor.org/rfc/rfc8032>
- **Licence :** les « Code Components » de la RFC (son §6) sont publiés sous la
  licence BSD simplifiée de l'IETF Trust (Trust Legal Provisions,
  <https://trustee.ietf.org/license-info>)
- **Ce qui est repris :** l'algorithme du §5.1 et les cinq vecteurs d'essai du
  §7.1 (`tests/donnees/externes/rfc8032-ed25519.json`, qui ne part pas au cabinet). Le
  code est écrit en français, en Python pur ; qu'il reprenne ou non la structure
  du §6, la mention figure ici et dans l'en-tête du module, pour ne laisser aucun
  doute sur une copie livrée chez un client.
