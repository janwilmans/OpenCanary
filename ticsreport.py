"""TICS report V2: takes a pre-filtered TICS-data-file (converted by ticstool.py and ticsfilter.py) and sends email to hardcoded receivers.
"""

from __future__ import print_function
import os, sys, re, urllib
import getopt
import tempfile
import traceback
import subprocess

import smtplib, os
import mimetypes

from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders

from socket import gethostname

# print to stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def CreateAttachment(file):
    fp = open(file, 'rb')
    content = fp.read()
    fp.close()
    return CreateBinaryPayload(content, 'application/octet-stream', file)

def CreateBinaryPayload(content, ctype, filename = ''):
    maintype, subtype = ctype.split('/', 1)
    img = MIMEBase(maintype, subtype)
    img.set_payload(content)
    if not filename == '':
        img.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filename))
    return img

def SendMail_internal(sender, recipients, subject, smtpName, message, attachments = []):
    if not isinstance(recipients, list):
        print("recipients should be a list");
        return

    if not isinstance(attachments, list):
        print("attachments should be a list");
        return

    # Create the container (outer) email message.
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ",".join(recipients)
    msg.preamble = subject

    msg.attach(CreateBinaryPayload(message, 'text/html'))

    for file in attachments:
        msg.attach(CreateAttachment(file))

    #encoders.encode_base64(msg)
    s = smtplib.SMTP(smtpName)
    s.sendmail(sender, recipients, msg.as_string())
    s.quit()
    
# using blat 
def GetBlatCommand():
    return r"\blat.exe";

def SendMail(sender, recipients, subject, smtpName, message, attachments = []):
    if not isinstance(recipients, list):
        print("recipients should be a list");
        return

    if not isinstance(attachments, list):
        print("attachments should be a list");
        return
    
    tempFilename = message
    if not message.endswith(".html"):    
        fd, tempFilename = tempfile.mkstemp()
        f = open(tempFilename, 'w+').write(message)
        os.close(fd)

    cmd = GetBlatCommand() + " " + tempFilename + " -server " + smtpName + " -f \"" + sender + "\" -s \"" + subject + "\""
    for attachment in attachments:
        cmd = cmd + " -attach \"" + attachment + "\"" 
    joinedRecepients = ",".join(recipients)
    cmd = cmd + " -to " + joinedRecepients
    status = subprocess.call(cmd)

def getLogFiles(path):
    # returns a list of log files in the path
    files = []
    for name in os.listdir(path):
        fullname = os.path.join(path, name)
        if os.path.isfile(fullname):
            if (name.endswith(".log")):
                files.append(fullname)
    return files
       
#  SMTP server at ""
smtpserver = "smtp.localserver";

senderAddress = "TICS Server <ticsserver@onmicrosoft.com>" 

# will be notified if this script fails
adminAddresses = ["foo.bar@onmicrosoft.com"]

# return a list of recipients
def notificationAddresses():
    recipients = ['receives@company.onmicrosoft.com']
    return recipients

def getHtmlStyles():
    return """
    <head>
<meta http-equiv="Content-Type" content="text/html; charset=windows-1250">
<style type="text/css">
body { font-family: Calibri, Arial;}
td { font-size: 85%; }
.hideextra { white-space: nowrap; overflow: hidden; text-overflow:ellipsis; }
</style>
</head>"""

def stripSqlEscapingWord(word):
    result = word
    if word.startswith('b"'):
        result = word[1:]
    if word.startswith("b'"):
        result = word[1:]
    return result.strip('"').strip("'")

def stripSqlEscaping(line):
    result = []
    for word in line:
        result += [stripSqlEscapingWord(word)]
    return result
    
def createHtmlReport(lines, filename, allMotionIssuesCount):
    f = open(filename, 'w+')
    f.write(r'<!DOCTYPE html><html>')
    f.write(getHtmlStyles())
    f.write(r'<body>')
    f.write(r'From the total number of issues found (' + str(allMotionIssuesCount) + r'), the following are found relevant for this report:')
    f.write(r'<a href="http://sw-wiki/index.php/tics/"><h2> Issue report</h2></a>')
    f.write(r'<table align="left">')
    f.write(r'<thead><tr>')
    f.write(r'<th title="#0" align="left">Prio</th>')
    f.write(r'<th title="#1" align="left">Team</th>')
    f.write(r'<th title="#2" align="left">Component</th>')
    f.write(r'<th title="#3" align="left">File</th>')
    f.write(r'<th title="#5" align="left">Source</th>')
    f.write(r'<th title="#6" align="left">Rule</th>')
    f.write(r'<th title="Wiki" align="left">Wiki</th>')
    f.write(r'<th title="#7" align="left">Level</th>')
    f.write(r'<th title="#8" align="left">Category</th>')
    f.write(r'<th title="#9" align="left">Description</th>')
    f.write(r'</tr></thead>')
    f.write(os.linesep)

    td = r'<td align="left"><div class="hideextra">'
    
    for line in lines:
        f.write('<tr>')
        parts = stripSqlEscaping(line.strip().split("|"))
        f.write(td + parts[0] + '</td>')
        f.write(td + parts[1] + '</td>')
        f.write(td + parts[2] + '</td>')
        f.write(td + parts[3] + ':' + parts[4] + '</td>')
        f.write(td + parts[5] + '</td>')
        if "CODINGSTANDARD" in parts[5] or "ABSTRACTINTERPRETATION" in parts[5]:
            if parts[10] == "":
                f.write(td + parts[6] + '</td>')
            else:
                f.write(td + r'<a href="' + parts[10] + '">' + parts[6] + '</a></td>')
        else:
            f.write(td + parts[6] + '</td>')
        
        # #-signs cannot be part of valid wiki-links
        rule = parts[6].replace("#", "_")
        
        f.write(td + r'<a href="http://sw-wiki/index.php/tics/rules/' + rule + '">' + 'Wiki</a></td>')
        f.write(td + parts[7] + '</td>')
        f.write(td + parts[8] + '</td>')
        
        #print parts
        if len(parts) < 11:
            eprint(parts)
            eprint("Line contains only ", len(parts))

        if "CODINGSTANDARD" in parts[5] or "ABSTRACTINTERPRETATION" in parts[5] or parts[10] == "":
            f.write(td + parts[9] + '</td>')
        else:
            f.write(td + r'<a href="' + parts[10] + '">' + parts[9] + '</a></td>')
        f.write('</tr>\n')
    
    f.write(r'</table>')
    f.write(r'</body></html>')
    f.write(os.linesep)
    f.close()
        
# tricks for finding high-prio issues
# - three (or more) consecutive lines with the same error
# - the same class name mentioned more then three times
# - assert(pointer); to detect null-pointers will prevent crash and cause a hanging process?

def TopNFilter(lines, count):
    return lines[:count]

def report(all_motion_issues, valueable_motion_issues, regression_motion_issues):
    global debugmode

    attachments = [all_motion_issues]
    allMotionIssuesCount = len(getFileContent(all_motion_issues))

    attachments += [valueable_motion_issues]
    filename = "ValueableMotionIssuesReport.html"
    body = filename
    attachments += [filename]
    createHtmlReport(TopNFilter(striplines(getFileContent(valueable_motion_issues)), 3000), filename, allMotionIssuesCount)

    body = "Great job. From the total number of issues found (' + str(allMotionIssuesCount) + r'), no issues are found relevant for this report."
    content = striplines(getFileContent(regression_motion_issues))
    length = len(content)
    if (length > 0): 
        filename = "RegressionMotionIssuesReport.html"
        attachments += [filename]
        createHtmlReport(content, filename, allMotionIssuesCount)
        body = filename

    if (length > 0): 
        print("Total Coding Standard violations:", length)
        subject = "TICS\\ticsreport.py: " + str(length) + " regression issue(s) found. (origin:" + gethostname() + ")"
        if not debugmode:
            message = open(filename, 'r').read()
            print("Send email to", notificationAddresses())
            SendMail(senderAddress, notificationAddresses(), subject, smtpserver, body, attachments)
    
def sendEmail(recipients, subject, message):
    print("Send email to", recipients)
    SendMail(senderAddress, recipients, subject, smtpserver, message)
   
def sendAdminEmail(subject, message):
    sendEmail(adminAddresses, subject, message)

def printUsage():
    print("ticsreport.py <all_motion_issues> <valueable_motion_issues> <regression_motion_issues> [/debug]")
    print("   [/debug] will not send emails but has otherwise identical behaviour")
    
def getFileContent(filename):
    with open(filename, "r") as f:
        lines = list(f)
    return lines

def striplines(lines):
    result = []
    for line in lines:
        result.append(line.strip())
    return result

def reportOnTics():
    if (len(sys.argv) < 4):
        printUsage()
        sys.exit(1)
        
    global debugmode
    debugmode = False
    for arg in sys.argv:
        if "/debug" in arg.lower():
            debugmode = True

    report(sys.argv[1], sys.argv[2], sys.argv[3])

def main():
    try:
        reportOnTics();
    except SystemExit as e:
        sys.exit(e)
    except:
        info = traceback.format_exc()
        print(info)
        sendAdminEmail("ticsreport.py exception", info)

if __name__ == "__main__":
    main()
    sys.exit(0)
