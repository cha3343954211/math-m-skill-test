#!/usr/bin/env python3
"""Send an email with one or more attachments via SMTP.

Credentials are read from env by default:
  SMTP_ADDRESS or QQ_MAIL_ADDRESS
  SMTP_AUTH_CODE or QQ_MAIL_AUTH_CODE

Example for QQ Mail:
  QQ_MAIL_ADDRESS='sender@example.com' QQ_MAIL_AUTH_CODE='code' \
  python send_smtp_attachment.py --smtp-host smtp.qq.com --smtp-port 465 --ssl \
    --subject 'Report' --body 'See attachment.' --attach report.pptx recipient@example.com
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
import ssl
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


def send(args: argparse.Namespace) -> None:
    sender = args.sender or os.environ.get("SMTP_ADDRESS") or os.environ.get("QQ_MAIL_ADDRESS")
    password = args.auth_code or os.environ.get("SMTP_AUTH_CODE") or os.environ.get("QQ_MAIL_AUTH_CODE")
    if not sender:
        raise SystemExit("Missing sender: set SMTP_ADDRESS/QQ_MAIL_ADDRESS or pass --sender")
    if not password:
        raise SystemExit("Missing auth code/password: set SMTP_AUTH_CODE/QQ_MAIL_AUTH_CODE or pass --auth-code")

    attachments = [Path(p) for p in args.attach]
    msg = build_message(sender, args.recipients, args.subject, args.body, attachments)

    if args.ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(args.smtp_host, args.smtp_port, context=context, timeout=args.timeout) as server:
            server.login(sender, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=args.timeout) as server:
            if args.starttls:
                server.starttls(context=ssl.create_default_context())
            server.login(sender, password)
            server.send_message(msg)

    print(f"Sent to {len(args.recipients)} recipient(s): {', '.join(args.recipients)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipients", nargs="+", help="Recipient email addresses")
    parser.add_argument("--sender", help="Sender email address")
    parser.add_argument("--auth-code", help="SMTP password/app password/auth code")
    parser.add_argument("--smtp-host", default="smtp.qq.com")
    parser.add_argument("--smtp-port", type=int, default=465)
    parser.add_argument("--ssl", action="store_true", default=True, help="Use implicit SSL; default true")
    parser.add_argument("--no-ssl", dest="ssl", action="store_false")
    parser.add_argument("--starttls", action="store_true", help="Use STARTTLS with plain SMTP")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--attach", action="append", default=[], help="Attachment path; repeatable")
    args = parser.parse_args()
    send(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
