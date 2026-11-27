# Crawlvora ažuriranja

Windows: Update.exe. Linux: crawlvora-update. Zasebni klijenti ne povećavaju veličinu glavnih instalacijskih paketa. Instalacijski EXE može biti bez Authenticode potpisa; manifest nadogradnje mora biti potpisan Ed25519 ključem ugrađenim u klijent.

Nakon objave v8.1.7, primjer za instalirano Online izdanje v8.1.6:

    Update.exe --tag v8.1.7-online --installed 8.1.6 --edition Online --package setup --staging update-817 --install
    ./crawlvora-update --tag v8.1.7-online --installed 8.1.6 --edition Online --package deb --staging update-817 --install

Bez --install paket se preuzima i verificira. Uz --staged --install postojeća priprema ponovno se verificira. Instaliranje traži potvrdu korisnika. Portable paket se priprema, ali se ne zamjenjuje automatski. Prije nadogradnje zatvorite aplikaciju i provjerite sigurnosnu kopiju.

Privatni ključ manifesta pohranjen je izvan repozitorija, u zaštićenom vlasničkom Windows spremištu i GitHub Actions secretu. Ne izlaže se buildovima. Gubitak ključa zahtijeva zaseban postupak obnove povjerenja; ne rotirati ga bez plana. Prvi updater preuzmite iz pouzdanog službenog izdanja.

Klijent trenutno zahtijeva eksplicitnu verziju, izdanje i vrstu paketa. Automatsko otkrivanje izdanja iz aplikacije, rollback nakon neuspješne instalacije i automatska zamjena portable paketa nisu dovršeni. Produkcijska instalacija na oba sustava zahtijeva zasebne završne testove.
