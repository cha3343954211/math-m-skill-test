import os, ssl, smtplib
from pathlib import Path
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
sender = os.environ.get('QQ_MAIL_ADDRESS') or os.environ.get('SMTP_ADDRESS')
password = os.environ.get('QQ_MAIL_AUTH_CODE') or os.environ.get('SMTP_AUTH_CODE')
recipient = 'recipient@example.com'
if not sender or not password:
    raise SystemExit('Missing QQ_MAIL_ADDRESS/SMTP_ADDRESS or auth code')
root = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012B')
attachments = [root/'支撑材料/papper/论文.pdf', root/'2012B_支撑材料.zip']
for p in attachments:
    if not p.exists():
        raise SystemExit(f'Missing attachment: {p}')
msg = EmailMessage()
msg['From'] = sender
msg['To'] = recipient
msg['Date'] = formatdate(localtime=True)
msg['Message-ID'] = make_msgid()
msg['Subject'] = '2012B太阳能小屋数学建模论文与支撑材料（优化版，以本封为准）'
msg.set_content('你好，\n\n附件为2012B太阳能小屋数学建模论文与支撑材料优化版。\n本版已将正式PDF扩充并重排为17页A4，补充数据清洗、算法步骤、完整分组结果、约束核验、误差来源与双目标解释；请以本封邮件为准。\n\n附件：\n1. 论文.pdf\n2. 2012B_支撑材料.zip\n')
for p in attachments:
    data=p.read_bytes()
    subtype='pdf' if p.suffix.lower()=='.pdf' else 'zip'
    maintype='application'
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)
with smtplib.SMTP_SSL('smtp.qq.com', 465, context=ssl.create_default_context(), timeout=90) as s:
    s.login(sender, password)
    s.send_message(msg)
print('Sent optimization version to 1 recipient(s):', recipient)
