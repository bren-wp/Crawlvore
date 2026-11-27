import tempfile
import unittest
import uuid
import smtplib
from pathlib import Path
from unittest.mock import patch
from core import Store
from crawlvora_mail import MailService
from native_vault import NativeVault, VaultUnavailable

class MemoryVault:
    def __init__(self): self.value=None
    def load(self): return self.value
    def save(self,value): self.value=dict(value)

class MailTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        self.store=Store(root/'db.sqlite')
        self.vault=MemoryVault()
        self.service=MailService(self.store,root,self.vault)
        with self.store.db() as db:
            self.store.upsert(db,{'title':'Synthetic recipient','email':'contact@example.invalid'})
            self.company=db.execute('SELECT id FROM companies').fetchone()[0]
        self.settings={'host':'smtp.example.invalid','port':587,'username':'sender','password':'synthetic-test-secret','sender':'sender@example.invalid','confirmed':True}
        self.service.configure(self.settings)
    def message(self,**changes):
        return dict({'company_id':self.company,'recipient':'contact@example.invalid','subject':'Test','body':'Synthetic notice','basis':'consent','confirmed':True,'request_id':str(uuid.uuid4())},**changes)
    def test_secret_not_returned_and_vault_names_are_separate(self):
        self.assertNotIn('password',self.service.settings())
        root=Path(self.store.path).parent
        self.assertEqual(len({NativeVault(root,p).identity for p in ('backup','registry','mail')}),3)
        self.assertFalse(self.service.forget()['configured'])
    def test_no_plaintext_fallback(self):
        with patch.object(self.vault,'save',side_effect=VaultUnavailable('test')):
            with self.assertRaises(ValueError): self.service.configure(self.settings)
    def test_rejects_multiple_addresses_and_changed_recipient(self):
        for recipient in ('a@example.invalid,b@example.invalid','other@example.invalid','a@example.invalid\nBcc: other@example.invalid'):
            with self.subTest(recipient=recipient), patch('crawlvora_mail.smtplib.SMTP') as smtp:
                with self.assertRaises(ValueError): self.service.send(self.message(recipient=recipient))
                smtp.assert_not_called()
    def test_rejects_unconfirmed_invalid_basis_and_header_injection(self):
        for changes in ({'confirmed':False},{'basis':'mass_marketing'},{'subject':'Subject\nBcc: someone@example.invalid'}):
            with patch('crawlvora_mail.smtplib.SMTP') as smtp:
                with self.assertRaises(ValueError): self.service.send(self.message(**changes))
                smtp.assert_not_called()
    def test_tls_and_idempotence_and_cooldown(self):
        data=self.message()
        with patch('crawlvora_mail.smtplib.SMTP') as smtp:
            conn=smtp.return_value
            conn.send_message.return_value={}
            self.assertEqual(self.service.send(data)['state'],'accepted')
            context=conn.starttls.call_args.kwargs['context']
            self.assertTrue(context.check_hostname)
            self.assertEqual(conn.send_message.call_args.kwargs['to_addrs'],['contact@example.invalid'])
            self.assertLess([x[0] for x in conn.method_calls].index('starttls'),[x[0] for x in conn.method_calls].index('login'))
            for item in (data,self.message()):
                with self.assertRaises(ValueError): self.service.send(item)
            smtp.assert_called_once()
        self.assertEqual(self.service.history(self.company)[0]['state'],'accepted')
    def test_unknown_delivery_not_retried(self):
        with patch('crawlvora_mail.smtplib.SMTP') as smtp:
            smtp.return_value.send_message.side_effect=smtplib.SMTPServerDisconnected('test')
            self.assertEqual(self.service.send(self.message())['state'],'unknown')
            smtp.assert_called_once()
    def test_blocklist_prevents_send(self):
        self.service.block({'recipient':'contact@example.invalid','confirmed':True})
        with patch('crawlvora_mail.smtplib.SMTP') as smtp:
            with self.assertRaises(ValueError): self.service.send(self.message())
            smtp.assert_not_called()
    def test_rejects_unencrypted_port(self):
        with self.assertRaises(ValueError): self.service.configure(dict(self.settings,port=25))
