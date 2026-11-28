# Redovna kompaktna distribucija (važeća politika)

Redovna izdanja sada obavezno sadrže četiri paketa bez ugrađene baze: Windows NSIS i Portable, Linux DEB i TAR.GZ. Oba updatera, izvorni ZIP, veličine paketa, potpisani manifest i SHA-256 čine ukupno 11 datoteka. Preuzimanje hrvatske baze i osvježavanje odvijaju se u aplikaciji s ovlaštenim pristupom; postojeća baza nikada se ne zamjenjuje praznom. Opcija u Zadaci i raspored dopušta automatsko preuzimanje nakon nadogradnje. Svježa instalacija bez ovlaštenog pristupa ne može automatski preuzeti podatke. Stari Full ugovor u nastavku ostaje samo za zasebnu, privatnu distribuciju uz odobrenje; nije uvjet redovnog izdanja.

## Obavezna objava svakog dovršenog razvojnog ciklusa

Svaki ciklus završen spajanjem u main mora isporučiti novo, verificirano stabilno GitHub izdanje. Prije spajanja pripremiti novu verziju koja je veća od zadnje objavljene, uskladiti sve verzijske oznake i završiti testove. Push u main pokreće kompletan postupak objave, bez iznimki zbog vrste promijenjenih datoteka. Ne objavljuje se nepotpuno izdanje, niti se postojeće stabilno izdanje prepisuje. Ako provjera ili objava ne uspije, ciklus nije završen; popraviti uzrok i ponovno pokrenuti provjere. PR sam po sebi nije izdanje.

### Točan popis obaveznih datoteka (11/11)

| Datoteka | Sadržaj |
|---|---|
| Setup-HR-Online.exe | Windows NSIS installer |
| Portable-HR-Online.exe | Windows Portable |
| Crawlvora-Linux-HR-Online-amd64.deb | Linux installer |
| Crawlvora-Linux-HR-Online-x86_64.tar.gz | Linux Portable |
| Update.exe | Windows updater |
| crawlvora-update | Linux updater |
| Crawlvora-source.zip | Izvorni kod |
| PACKAGE-SIZES.json | Veličine paketa |
| UPDATE-MANIFEST.json | Manifest nadogradnje |
| UPDATE-MANIFEST.sig | Ed25519 potpis manifesta |
| SHA256SUMS.txt | Kontrolni sažeci svih ostalih datoteka |

Svi paketi bez ugrađene baze. Maksimalna početna veličina svakog aplikacijskog paketa je 45 decimalnih MB. Svi paketi moraju pripadati istom commitu i proći odgovarajuće Windows/Linux testove. Oba updatera su obavezna; potpis manifesta i provjera SHA-256 ne smiju se zaobići čak ni ako izvršne datoteke nemaju potpis izdavača. Objavljuje se tek nakon lokalne provjere 11 datoteka, provjere stanja, veličine i SHA-256 svih udaljenih asseta te provjere konačne oznake verzije i commita. Završna CI provjera mora potvrditi uspješnu objavu. Stabilno izdanje s postojećim rendererom nije dokaz dovršene nativne migracije.

Privatni Full paketi nisu dio redovne distribucije. Eventualna zasebna distribucija baze zahtijeva prethodno odobrenje privatnosti i zasebne provjere. Ne uključivati podatkovne snimke ni pristupne podatke u javna izdanja.
