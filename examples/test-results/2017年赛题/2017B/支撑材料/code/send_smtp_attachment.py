#!/usr/bin/env python3
"""Send an email with one or more attachments via SMTP.
Credentials are read from env by default:
  SMTP_ADDRESS or QQ_MAIL_ADDRESS
  SMTP_AUTH_CODE or QQ_MAIL_AUTH_CODE
"""
from __future__ import annotations
import argparse, mimetypes, os, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path

def build_message(sender: str, recipients: list[str], subject: str, body: str, attachments: list[Path]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {path}")
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg

def send(args):
    sender = args.sender or os.environ.get("SMTP_ADDRESS") or os.environ.get("QQ_MAIL_ADDRESS")
    password = args.auth_code or os.environ.get("SMTP_AUTH_CODE") or os.environ.get("QQ_MAIL_AUTH_CODE")
    if not sender: raise SystemExit("Missing sender")
    if not password: raise SystemExit("Missing auth code/password")
    msg = build_message(sender, args.recipients, args.subject, args.body, [Path(p) for p in args.attach])
    if args.ssl:
        with smtplib.SMTP_SSL(args.smtp_host, args.smtp_port, context=ssl.create_default_context(), timeout=args.timeout) as server:
            server.login(sender, password); server.send_message(msg)
    else:
        with smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=args.timeout) as server:
            if args.starttls: server.starttls(context=ssl.create_default_context())
            server.login(sender, password); server.send_message(msg)
    print(f"Sent to {len(args.recipients)} recipient(s): {', '.join(args.recipients)}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("recipients", nargs="+")
    p.add_argument("--sender"); p.add_argument("--auth-code")
    p.add_argument("--smtp-host", default="smtp.qq.com"); p.add_argument("--smtp-port", type=int, default=465)
    p.add_argument("--ssl", action="store_true", default=True); p.add_argument("--no-ssl", dest="ssl", action="store_false")
    p.add_argument("--starttls", action="store_true"); p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--subject", required=True); p.add_argument("--body", required=True); p.add_argument("--attach", action="append", default=[])
    send(p.parse_args()); return 0
if __name__ == "__main__": raise SystemExit(main())
