# Uklanjanje početnog CSV uvoza

Stara baza nije dio aktivnog izvornog koda niti novih instalacijskih paketa. Povijest Gita nije prepisana.

Alat src/legacy_cleanup.py prihvaća isključivo originalnu CSV datoteku čiji se SHA-256 podudara s početnim uvozom. Zadano samo pregledava zapise. Opcija --apply zahtijeva zatvorenu aplikaciju, ekskluzivni lock, provjerenu sigurnosnu kopiju i ponovnu provjeru kandidata.

    python src/legacy_cleanup.py /putanja/companies.sqlite3 /putanja/original.csv
    python src/legacy_cleanup.py /putanja/companies.sqlite3 /putanja/original.csv --apply

Uklanjaju se samo nepromijenjeni zapisi koji pripadaju izvornom CSV-u, bez drugih izvora, povijesti ili povezanih podataka. Zapisi povezani sa službenom bazom zadržavaju se. Ovaj postupak ne uklanja pojedinačna naslijeđena polja već spojenih subjekata niti briše stare sigurnosne kopije.

Ako je aplikacija otvorena, postupak se zaustavlja bez izmjene baze.
