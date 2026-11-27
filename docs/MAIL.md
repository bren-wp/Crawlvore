# Crawlvora Mail

Open a company profile and choose **Sastavi e-poštu** beside the recorded address. Configure SMTP with your own authenticated sender, using TLS 465 or STARTTLS 587. Credentials are stored via Windows DPAPI or Linux Secret Service in a separate vault namespace; there is no plaintext fallback. The password is not returned by the configuration API.

The security template is a general warning about suspicious payment requests, not a claim that a particular company committed fraud. Review the content and confirm the exact recipient, your appropriate basis for contacting them, and the final send. Public registry contact data alone is not consent. The interface does not verify external consent records or legal compliance; the operator must do so. No mailing lists, automatic campaigns or bulk send. A suppression list blocks future sending to an address. One attempt per minute and at most twenty attempts per 24 hours within each workspace.

The local audit log records recipient, subject, declared basis, time and SMTP status, not the message body or password. Accepted means the SMTP server accepted the submission, not that the recipient read or received it. Pending/unknown states must be reviewed manually; there is no automatic retry. Keep audit data in the protected local workspace, apply an appropriate retention policy, and restrict access to backups.

Automated tests mock SMTP. Real provider compatibility, credentials and actual delivery require separate acceptance with an authorized test mailbox.
