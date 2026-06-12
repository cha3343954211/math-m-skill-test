#!/usr/bin/env python3
from __future__ import annotations
import argparse, mimetypes, os, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path

def build_message(sender, recipients, subject, body, attachments):
    msg=EmailMessage(); msg['From']=sender; msg['To']=', '.join(recipients); msg['Subject']=subject; msg.set_content(body)
    for path in attachments:
        path=Path(path)
        if not path.exists(): raise FileNotFoundError(path)
        ctype, encoding=mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None: ctype='application/octet-stream'
        maintype, subtype=ctype.split('/',1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('recipients', nargs='+'); ap.add_argument('--sender'); ap.add_argument('--auth-code'); ap.add_argument('--smtp-host', default='smtp.qq.com'); ap.add_argument('--smtp-port', type=int, default=465); ap.add_argument('--ssl', action='store_true', default=True); ap.add_argument('--timeout', type=int, default=60); ap.add_argument('--subject', required=True); ap.add_argument('--body', required=True); ap.add_argument('--attach', action='append', default=[])
    a=ap.parse_args(); sender=a.sender or os.environ.get('SMTP_ADDRESS') or os.environ.get('QQ_MAIL_ADDRESS'); password=a.auth_code or os.environ.get('SMTP_AUTH_CODE') or os.environ.get('QQ_MAIL_AUTH_CODE')
    if not sender: raise SystemExit('Missing sender')
    if not password: raise SystemExit('Missing auth code')
    msg=build_message(sender,a.recipients,a.subject,a.body,[Path(x) for x in a.attach])
    context=ssl.create_default_context()
    with smtplib.SMTP_SSL(a.smtp_host,a.smtp_port,context=context,timeout=a.timeout) as server:
        server.login(sender,password); server.send_message(msg)
    print(f"Sent to {len(a.recipients)} recipient(s): {', '.join(a.recipients)}")
if __name__=='__main__': main()
