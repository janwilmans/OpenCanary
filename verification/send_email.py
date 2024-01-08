#!/usr/bin/env python3
""" send an email report
"""

import traceback
import sys
import os
from subprocess import Popen, PIPE

import smtplib

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


def CreateBinaryPayload(content, ctype, filename=''):
    maintype, subtype = ctype.split('/', 1)
    img = MIMEBase(maintype, subtype)
    img.set_payload(content)
    if not filename == '':
        img.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filename))
    return img


def execute_popen(list):
    sub_process = Popen(list, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    (std_out, std_err) = sub_process.communicate()
    sub_process.wait()
    exitcode = sub_process.returncode
    return std_out, std_err, exitcode


def getRecentEditors():
    list = ['git', 'log', '--since', '2.week']
    stdout, stderr, returncode = execute_popen(list)
    result = []
    for line in set(stdout.splitlines()):
        if 'Author:' in line:
            parts = line.replace(">", "").split("<")
            if len(parts) == 2:
                result += [parts[1]]
    return result


def filterList(editors):
    auto_send_authors = ["firstname1.lastname1", "firstname2.lastname2"]
    result = []
    for item in editors:
        for author in auto_send_authors:
            if author in item:
                result += [item]
    return result


def listContains(list, name):
    for item in list:
        if name in item:
            return True
    return False


def sendReport(bodyfile, attachments=[]):
    global recipients

    recipients = filterList(getRecentEditors())
    if len(recipients) < 1:
        recipients = ["some@email.address.com"]

    if is_scheduled_build():
        recipients = ["some1@email.address.com"]

    if is_part_of_project("tin"):
        recipients = ["some3@email.address.com"]

    if not on_ci_server():
        # send to admin only for testing
        recipients = ["someadmin@email.address.com"]

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message['To'] = ",".join(recipients)
    message["Subject"] = subject
    # message["Bcc"] = receiver_email  # Recommended for mass emails

    with open(bodyfile, encoding="utf-8") as f:
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
    # server.starttls()      # uncomment to use TLS
    # server.ehlo()
    if len(login_password) > 0:
        server.login(login_name, login_password)
    try:
        sprint("Sending email [" + subject + "] to", recipients)
        server.sendmail(sender_email, recipients, message.as_string())
        sprint("Done.")
        server.quit()
    except smtplib.SMTPRecipientsRefused as ex:
        sprint("Email [" + subject + "] was NOT send, exception caught:", getattr(ex, 'message', repr(ex)))


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " <bodyfile> <attachments...> [-s <subject>]")
    eprint("   will send an email to hardcoded recipients ")


def main():
    global subject
    if len(sys.argv) < 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    att = []
    captureSubject = False
    if len(sys.argv) > 2:
        for arg in sys.argv[2:]:
            if arg == "-s":
                captureSubject = True
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
        show_usage()
        sys.exit(1)
