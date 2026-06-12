from __future__ import annotations
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

sender = os.environ.get('QQ_MAIL_ADDRESS', 'sender@example.com')
auth = os.environ.get('QQ_MAIL_AUTH_CODE')
recipient = 'recipient@example.com'
root = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014A')
pdf = root / '支撑材料' / 'papper' / '论文.pdf'
zip_path = root / '2014A_支撑材料完整包.zip'
if not auth:
    raise SystemExit('Missing QQ_MAIL_AUTH_CODE')
for p in [pdf, zip_path]:
    if not p.exists():
        raise FileNotFoundError(p)

msg = EmailMessage()
msg['From'] = sender
msg['To'] = recipient
msg['Subject'] = '2014A嫦娥三号软着陆数学建模论文与支撑材料'
msg.set_content('''你好，附件为 2014A「嫦娥三号软着陆轨道设计与控制策略」数学建模成果：\n\n1. 论文.pdf\n2. 2014A_支撑材料完整包.zip\n\n支撑材料包含完整代码、原始数据复制、图表、结果表、frozen_numbers.json 和 LaTeX 源文件。\n\n—— Hermes Agent / Hermes Agent''')
for path in [pdf, zip_path]:
    ctype, enc = mimetypes.guess_type(str(path))
    if ctype is None or enc is not None:
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

with smtplib.SMTP_SSL('smtp.qq.com', 465, context=ssl.create_default_context(), timeout=120) as s:
    s.login(sender, auth)
    s.send_message(msg)
print(f'Sent mail from {sender} to {recipient} with attachments: {pdf.name} ({pdf.stat().st_size} bytes), {zip_path.name} ({zip_path.stat().st_size} bytes)')
