"""Explicit, single-recipient correspondence with authenticated TLS SMTP."""
import re
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from native_vault import NativeVault, VaultUnavailable

ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_{}|~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
HOST = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
BASES = ("consent", "existing_correspondence", "security_notice")
TEMPLATES = {
    "custom": {"subject": "", "body": ""},
    "security": {
        "subject": "Sigurnosno upozorenje – provjerite sumnjive poruke",
        "body": "Poštovani,\n\nAko primite sumnjiv zahtjev za uplatu ili promjenu bankovnih podataka, provjerite ga putem neovisnog, prethodno poznatog kontakta. Ne otvarajte neprovjerene poveznice i privitke te ne dijelite lozinke.\n\nSrdačan pozdrav"
    }
}

def address(value):
    if not isinstance(value, str) or len(value) > 254 or not ADDRESS.fullmatch(value):
        raise ValueError("Potrebna je jedna valjana adresa e-pošte.")
    return value

def config(data):
    host, port = data.get("host"), data.get("port")
    user, password = data.get("username"), data.get("password")
    if not isinstance(host, str) or len(host) > 253 or not HOST.fullmatch(host):
        raise ValueError("Unesite valjan naziv SMTP poslužitelja.")
    if type(port) is not int or port not in (465, 587):
        raise ValueError("Dopušteni su TLS priključci 465 i 587.")
    if not isinstance(user, str) or not 1 <= len(user) <= 254 or not user.isascii() or any(ord(c)<32 or ord(c)==127 for c in user):
        raise ValueError("Neispravno SMTP korisničko ime.")
    if not isinstance(password, str) or not 1 <= len(password) <= 2048 or not password.isascii() or any(ord(c)<32 or ord(c)==127 for c in password):
        raise ValueError("Neispravna SMTP lozinka ili aplikacijska lozinka.")
    return {"host": host, "port": port, "username": user, "password": password, "sender": address(data.get("sender"))}

class MailService:
    def __init__(self, store, workspace, vault=None):
        self.store = store
        self.vault = vault if vault is not None else NativeVault(workspace, purpose="mail")

    def initialize(self, db):
        db.execute("""CREATE TABLE IF NOT EXISTS mail_log (
            id TEXT PRIMARY KEY, company_id INTEGER NOT NULL, recipient TEXT NOT NULL,
            subject TEXT NOT NULL, basis TEXT NOT NULL, created INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('pending','accepted','unknown','rejected')))""")
        db.execute("CREATE INDEX IF NOT EXISTS mail_log_created ON mail_log(created)")
        db.execute("""CREATE TABLE IF NOT EXISTS mail_blocklist (
            recipient TEXT PRIMARY KEY, created INTEGER NOT NULL)""")

    def load(self):
        try:
            raw = self.vault.load()
        except VaultUnavailable:
            raise ValueError("Sigurna pohrana e-pošte nije dostupna.") from None
        return config(raw) if raw and raw.get("host") else None

    def settings(self):
        try:
            current = self.load()
        except ValueError:
            return {"configured": False, "vault_available": False}
        return {"configured": bool(current), "vault_available": True, **(
            {k: current[k] for k in ("host", "port", "username", "sender")} if current else {}
        )}

    def configure(self, data):
        if data.get("confirmed") is not True:
            raise ValueError("Potvrdite spremanje u sigurnu pohranu.")
        current = config(data)
        try:
            self.vault.save(current)
        except VaultUnavailable:
            raise ValueError("Postavke nisu spremljene: sigurna pohrana nije dostupna.") from None
        return self.settings()

    def forget(self):
        # Overwrite the encrypted record; never retain plaintext credentials.
        try:
            self.vault.save({})
        except VaultUnavailable:
            raise ValueError("Uklanjanje pristupnih podataka nije potvrđeno.") from None
        return self.settings()

    def block(self, data):
        recipient = address(data.get("recipient")).lower()
        if data.get("confirmed") is not True:
            raise ValueError("Potvrdite zabranu budućeg slanja.")
        with self.store.db() as db:
            self.initialize(db)
            db.execute("INSERT OR IGNORE INTO mail_blocklist VALUES (?,?)", (recipient, int(time.time())))
        return {"ok": True}

    def history(self, company_id):
        if type(company_id) is not int or company_id < 1:
            raise ValueError("Neispravan subjekt.")
        with self.store.db() as db:
            self.initialize(db)
            return [dict(row) for row in db.execute(
                "SELECT id,recipient,subject,basis,created,state FROM mail_log WHERE company_id=? ORDER BY created DESC,id DESC LIMIT 50", (company_id,))]

    def send(self, data):
        if data.get("confirmed") is not True or data.get("basis") not in BASES:
            raise ValueError("Potvrdite dopuštenje i svrhu kontakta.")
        recipient, subject, body = address(data.get("recipient")), data.get("subject"), data.get("body")
        company_id = data.get("company_id")
        if type(company_id) is not int or company_id < 1:
            raise ValueError("Odaberite poslovni subjekt.")
        if not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 200 or any(ord(c)<32 or ord(c)==127 for c in subject):
            raise ValueError("Neispravan predmet poruke.")
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 12000 or "\x00" in body:
            raise ValueError("Neispravan sadržaj poruke.")
        try:
            request_id = str(uuid.UUID(data.get("request_id", "")))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Neispravan identifikator slanja.") from None
        current = self.load()
        if not current:
            raise ValueError("Najprije postavite SMTP pristup.")
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = current["sender"], recipient, subject.strip()
        message["Message-ID"] = "<"+request_id+"@"+current["sender"].split("@")[1]+">"
        message.set_content(body)
        now = int(time.time())
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            self.initialize(db)
            company = db.execute("SELECT email FROM companies WHERE id=?", (company_id,)).fetchone()
            if not company or company[0].strip() != recipient:
                raise ValueError("Adresa se promijenila. Ponovno otvorite profil tvrtke.")
            if db.execute("SELECT 1 FROM mail_blocklist WHERE recipient=?", (recipient.lower(),)).fetchone():
                raise ValueError("Primatelj je na popisu zabrane slanja.")
            previous = db.execute("SELECT state FROM mail_log WHERE id=?", (request_id,)).fetchone()
            if previous:
                raise ValueError("Ovaj zahtjev već je evidentiran; nema automatskog ponavljanja.")
            if db.execute("SELECT 1 FROM mail_log WHERE created>=? LIMIT 1", (now-60,)).fetchone():
                raise ValueError("Između poruka mora proći najmanje jedna minuta.")
            if db.execute("SELECT count(*) FROM mail_log WHERE created>=?", (now-86400,)).fetchone()[0] >= 20:
                raise ValueError("Dosegnuto je dnevno ograničenje od 20 poruka.")
            db.execute("INSERT INTO mail_log VALUES (?,?,?,?,?,?,?)", (
                request_id, company_id, recipient, subject.strip(), data["basis"], now, "pending"))
        # No retries: an interrupted SMTP DATA transaction may already have delivered.
        state = "unknown"
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            if current["port"] == 465:
                connection = smtplib.SMTP_SSL(current["host"], 465, timeout=15, context=context)
            else:
                connection = smtplib.SMTP(current["host"], 587, timeout=15)
            try:
                if current["port"] == 587:
                    connection.ehlo()
                    connection.starttls(context=context)
                    connection.ehlo()
                connection.login(current["username"], current["password"])
                refused = connection.send_message(message, from_addr=current["sender"], to_addrs=[recipient])
                state = "rejected" if refused else "accepted"
            finally:
                connection.close()
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPNotSupportedError):
            state = "rejected"
        except (smtplib.SMTPException, OSError):
            pass
        with self.store.db() as db:
            db.execute("UPDATE mail_log SET state=? WHERE id=?", (state, request_id))
        return {"id": request_id, "state": state}
