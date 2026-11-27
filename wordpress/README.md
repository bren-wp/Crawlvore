# Tvrtke za WordPress

Samostalni dodatak (prototip 0.1.0) za administratore: uvoz CSV-a, pretraživanje po MBS-u, OIB-u, nazivu i gradu, filtar e-pošte, Moje tvrtke i CSV izvoz odabira. Nema javnih endpointa, automatskog slanja e-pošte ni uključene baze. Podaci ostaju u WordPress bazi. Deaktivacija ne briše podatke.

Instalacija: zapakirati mapu `tvrtke` u ZIP, učitati kroz Dodaci → Dodaj novi. Uvoz prihvaća `mbs,title,oib,city,email` (mbs i title obavezni), najviše 50.000 redaka i 10 MiB po datoteci. Veći skupovi zahtijevaju odvojene uvoze. Koristiti samo podatke za koje postoji pravo korištenja; poslovna adresa e-pošte nije sama po sebi privola za marketing.

Prije produkcije: WordPress/MySQL/MariaDB integracijski testovi, izravna autorizirana API sinkronizacija, upravljanje privolama, predlošci i slanje e-pošte, potpuna sigurnosna provjera. Dodatak je odvojen od četiri desktop paketa i ne mijenja 11-datotečni ugovor izdanja.
