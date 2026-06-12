#!/usr/bin/env python
import argparse, mimetypes, os, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path

def build_message(sender, recipients, subject, body, attachments):
    msg=EmailMessage(); msg['From']=sender; msg['To']=', '.join(recipients); msg['Subject']=subject; msg.set_content(body)
    for path in attachments:
        path=Path(path)
        if not path.exists(): raise FileNotFoundError(path)
        ctype, enc=mimetypes.guess_type(str(path))
        if ctype is None or enc is not None: ctype='application/octet-stream'
        maintype, subtype=ctype.split('/',1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('recipients', nargs='+')
    ap.add_argument('--smtp-host', default='smtp.qq.com')
    ap.add_argument('--smtp-port', type=int, default=465)
    ap.add_argument('--timeout', type=int, default=60)
    ap.add_argument('--subject', required=True)
    ap.add_argument('--body', required=True)
    ap.add_argument('--attach', action='append', default=[])
    args=ap.parse_args()
    sender=os.environ.get('SMTP_ADDRESS') or os.environ.get('QQ_MAIL_ADDRESS')
    password=os.environ.get('SMTP_AUTH_CODE') or os.environ.get('QQ_MAIL_AUTH_CODE')
    if not sender or not password: raise SystemExit('Missing SMTP env')
    msg=build_message(sender,args.recipients,args.subject,args.body,args.attach)
    with smtplib.SMTP_SSL(args.smtp_host,args.smtp_port,context=ssl.create_default_context(),timeout=args.timeout) as s:
        s.login(sender,password); s.send_message(msg)
    print('Sent to '+', '.join(args.recipients))
if __name__=='__main__': main()
