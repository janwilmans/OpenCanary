#!/usr/bin/env python3
""" send an email report
"""

import traceback, sys, os, time

import email, smtplib

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from util import *

mailserver = 'gateway.company.com'
mailserver_port = 25
subject = "Software Quality Report"
sender_email = "sender@email.address.com"
recipients = ["some@email.address.com"]
login_name = sender_email
login_password = ""

def CreateBinaryPayload(content, ctype, filename = ''):
    maintype, subtype = ctype.split('/', 1)
    img = MIMEBase(maintype, subtype)
    img.set_payload(content)
    if not filename == '':
        img.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filename))
    return img

def sendReport(bodyfile, attachments = []):
    global recipients
    # send to admin only for testing 
    if not on_ci_server():
         recipients = ["jan.wilmans@kindtechnologies.nl"]

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message['To'] = ",".join(recipients)
    message["Subject"] = subject
    #message["Bcc"] = receiver_email  # Recommended for mass emails

    with open(bodyfile, "r") as f:
        if bodyfile.endswith(".html"):
            part = MIMEText(f.read(), "html")
        else:
            part = MIMEText(f.read(), "text")
        message.attach(part)

    for filename in attachments:

        # Open file in binary mode
        with open(filename, "rb") as attachment:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header('Content-Disposition', 'attachment', filename=filename)

        # Add attachment to message and convert message to string
        message.attach(part)

    # Log in to server using secure context and send email
    server = smtplib.SMTP(mailserver, mailserver_port)
    server.ehlo()
    #server.starttls()      # uncomment to use TLS
    #server.ehlo()
    if len(login_password) > 0:
        server.login(login_name, login_password)
    try:
        server.sendmail(sender_email, recipients, message.as_string())
        sprint("Email [" + subject + "] was send to", recipients)
        server.quit()
    except smtplib.SMTPRecipientsRefused as ex:
        sprint("Email [" + subject + "] was NOT send, exception caught:", getattr(ex, 'message', repr(ex)))

def showUsage():
    eprint("Usage: " + os.path.basename(__file__) + " <bodyfile> <attachments...> [-s <subject>]")
    eprint("   will send an email to hardcoded recipients ")

def main():
    global subject
    if len(sys.argv) < 2:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    att = []
    captureSubject = False
    if len(sys.argv) > 2:
        for arg in sys.argv[2:]:
            if arg == "-s":
                captureSubject = True;
                continue
            else:
                if captureSubject:
                    subject = arg
                    captureSubject = False
                    continue

                att += [arg]

    sendReport(sys.argv[1], att)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        showUsage()
        sys.exit(1)

