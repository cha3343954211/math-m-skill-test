import os, sys, ssl, smtplib
from pathlib import Path
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

sender = os.environ.get('QQ_MAIL_ADDRESS')
password = os.environ.get('QQ_MAIL_AUTH_CODE')
recipient = 'recipient@example.com'
if not sender or not password:
    raise SystemExit('Missing QQ_MAIL_ADDRESS or QQ_MAIL_AUTH_CODE')
root = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012A')
attachments = [root/'支撑材料/papper/论文.pdf', root/'2012A_支撑材料.zip']
for p in attachments:
    if not p.exists():
        raise SystemExit(f'Missing attachment: {p}')
msg = EmailMessage()
msg['From'] = sender
msg['To'] = recipient
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid()
msg['Subject'] = '2012A 葡萄酒的评价 数学建模论文与支撑材料'
msg.set_content('你好，\n\n附件为 2012A「葡萄酒的评价」数学建模论文 PDF 与完整支撑材料压缩包。\n\n包含：论文PDF、LaTeX源文件、可复现Python代码、结果表、图表、frozen_numbers.json 和 README。\n\n-- Hermes Agent/Hermes Agent')
for p in attachments:
    data = p.read_bytes()
    maintype = 'application'
    subtype = 'pdf' if p.suffix.lower()=='.pdf' else 'zip'
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)
context = ssl.create_default_context()
with smtplib.SMTP_SSL('smtp.qq.com', 465, context=context, timeout=60) as s:
    s.login(sender, password)
    s.send_message(msg)
print(f'SENT to {recipient}; attachments=' + ', '.join(p.name for p in attachments))
