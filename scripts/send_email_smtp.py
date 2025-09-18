#!/usr/bin/env python3
import os, smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
TO = os.getenv('SUMMARY_TO', 'yash.gokakkar@bitwiseglobal.com')
SUBJECT = os.getenv('SUMMARY_SUBJECT', 'POC QA Summary')

def main():
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise SystemExit("Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars")
    with open('summary.md', 'r', encoding='utf-8') as fh:
        body = fh.read()
    msg = EmailMessage()
    msg['Subject'] = SUBJECT
    msg['From'] = SMTP_USER
    msg['To'] = TO
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    print("Email sent to", TO)

if __name__ == '__main__':
    main()
