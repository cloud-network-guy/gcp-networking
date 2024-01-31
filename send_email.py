from flask import Flask
from flask_mail import Mail, Message
from asyncio import run
from main import get_version, get_settings
from check_ssl_certs import main
from smtplib import SMTP

app = Flask(__name__)
app.config.update(
	DEBUG=True,
	#EMAIL SETTINGS
	MAIL_SERVER='100.77.77.77',
	MAIL_PORT=25,
	MAIL_USE_SSL=False,
	#MAIL_USERNAME = 'your@gmail.com',
	#MAIL_PASSWORD = 'yourpassword'
)
mail = Mail(app)
"""
@app.route('/send-mail/')
def send_mail():

    sender = "jeheyer@att.net"
    recipients = ["jeheyer@me.com", "greenlakejohnny@gmail.com"]

    try:
        version = run(get_version({}))
        settings = run(get_settings())
        data = {} #run(main())
        msg = Message("Send Mail Tutorial!", sender=sender, recipients=recipients)
        msg.body = f"data is {data}"
        mail.send(msg)
        return 'Mail sent!'
    except Exception as e:
        quit(e)

"""
def send_mail():

    sender = "jeheyer@att.net"
    recipient = "jeheyer@me.com"
    output = {}

    version = run(get_version({}))
    settings = run(get_settings())
    data = {'test': 1}
    data = run(main())
    body = ""
    for item in data:
        project_id = item.get('project_id')
        project_id_link = f"https://console.cloud.google.com/home/dashboard?project={project_id}"
        body += project_id_link
        body += item.get('cn')
        body += item.get('expires')
        body += item.get('name')
        body += item.get('region')
        body += item.get('target_proxy')

    smtp_server = settings.get('smtp_server')
    smtp_port = settings.get('smtp_port')

    if recipient and data:
        subject = "SSL Certificates Expiring Soon"
        message = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{body}\n"
        try:
            server = SMTP(smtp_server, port=smtp_port)
            server.ehlo()
            server.sendmail(sender, recipient, message)
            server.quit()
        except Exception as e:
            print(e)
    else:
        print(output, end="")


if __name__ == "__main__":

    send_mail()