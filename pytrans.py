#!C:\Python27\python.exe
"""
# The MIT License (MIT)
#
# Copyright © 2022 by Carsten Busse carsten.busse@gmail.com
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sub-license, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
import os
import usb2lpt
import sys
import time

verbose = 0

debug = False

slomo = False

force = False

device = 0

sourcelist = None

"""
Example use of the usb2lpt class,
requires:
  -  Windows
  -  Python3.9+
  -  the hardware adapter of course
  -  an Atari Portfolio palmtop from 1989
  -  the HPC101 Parallel Port Interface of the Portfolio
  -  1:1 Parallel Port cable to connect the portfolio to the pc
"""
CONTROL_BUFSIZE = 100
LIST_BUFSIZE = 2000
PAYLOAD_BUFSIZE = 60000
MAX_FILENAME_LEN = 79

receiveInit = bytearray([0x06, 0x00, 0x70] + [0x00]*79) #  size is 82

receiveFinish = bytearray([0x20, 0x00, 0x03])

transmitInit = bytearray([0x03, 0x00, 0x70, 0x0c, 0x7a, 0x21, 0x32] + [0x00]*83) # size is 90

controlData = bytearray(CONTROL_BUFSIZE)

listbuf = bytearray(LIST_BUFSIZE)

payload = bytearray(PAYLOAD_BUFSIZE)

transmitOverwrite = bytearray([0x05, 0x00, 0x70])

transmitCancel = bytearray([0x00, 0x00, 0x00])

listbuf = bytearray(LIST_BUFSIZE)

sourcecount = 0

nReceivedFiles = 0

def waitClockHigh():
    byte = 0
    while not byte:
        print("waitClockHigh") if debug else None
        byte = myport.inStatus() & 0x20

def waitClockLow():
    byte = 1
    while byte:
        print("waitClockLow") if debug else None
        byte = myport.inStatus() & 0x20

def getBit():
    print("getbit") if debug else None
    return (myport.inStatus() & 0x10) >> 4

def receiveByte():
    i = 0
    byte = 0
    print("Receive Byte") if verbose>1 else None
    for i in range(4):
        print(f"Receive bitBang i:{i}  byte:{byte:02x}",end='\r') if verbose>1 else None
        waitClockLow()
        byte = (byte << 1) | getBit()
        myport.outData(0)
        waitClockHigh()
        byte = (byte << 1) | getBit()
        myport.outData(2)
    print("\n") if verbose>1 else None
    return byte

def sendByte(byte):
    if type(byte) == str:
        byte = bytes(byte,'utf-8')[0]
    i = 0
    b = 0
    time.sleep(0.001) if slomo else None
    print("Sending Byte") if debug else None
    time.sleep(0.05) if slomo else None
    for i in range(4):
        print(f"Send bitBang i:{i} byte:{byte}",end='\r') if verbose>1 else None
        b = ((byte & 0x80) >> 7) | 2
        myport.outData(b)
        b = (byte & 0x80) >> 7
        myport.outData(b)


        byte = byte << 1
        waitClockLow()

        b = (byte & 0x80) >> 7
        myport.outData(b)
        b = ((byte & 0x80) >> 7) | 2
        myport.outData(b)

        byte = byte << 1
        waitClockHigh()

def sendBlock(pData, length):
    byte = 0
    i = 0
    lenH = lenL = 0
    checksum = 0
    if length:
        byte = receiveByte()
        if chr(byte) == 'Z':
            print("Portfolio ready for receiving.") if verbose else None
        else:
            print("Portfolio not ready!") if verbose else None
            exit(1)
        time.sleep(0.05) if slomo else None  # = usleep(50000)
        sendByte(0xa5)
        lenH = length >> 8
        lenL = length & 0xff
        sendByte(lenL)
        checksum -= lenL
        sendByte(lenH)
        checksum -= lenH
        for i in range(length):
            byte = pData[i]
            sendByte(byte)
            checksum -= byte
            if verbose:
                print(f"Sent {i+1:06d} of {length:06d} bytes.",end='\r')
        sendByte(checksum&0xff)
        print("\n") if verbose else None
        byte = receiveByte()
        if byte == checksum&0xff:
            print("Checksum OK") if verbose else None
        else:
            print("Checksum Error") if verbose else None
            exit(1)

def receiveBlock(pData, maxLen):
    length = i = 0
    lenL = LenH = 0
    checksum = 0
    byte = 0

    sendByte('Z')
    byte = receiveByte()

    if byte == 0xa5:
        print("Ack OK") if verbose else None
    else:
        print(f"Ack ERR (got {byte:02x} instead of 0xA5)") if verbose else None
        exit(1)
    lenL = receiveByte()
    lenH = receiveByte()
    checksum += lenL
    checksum += lenH
    length = (lenH << 8) | lenL
    if length > maxLen:
        print(f"Receive Buffer too small ({maxLen} instead of {length} bytes)") if verbose else None
        return 0
    
    for i in range(length):
        byte = receiveByte()
        checksum += byte
        pData[i] = byte
        print(f"Received {i+1:06d} of {length:06d} bytes",end='\r') if verbose else None
    print("\n") if verbose else None

    byte = receiveByte()

    if (0x100 - byte) == (checksum & 0xff):
        print("checksum OK") if verbose else None
    else:
        print(f"checksum ERR {0x100-byte:02x} vs {checksum:02x}")
        exit(1)
    time.sleep(0.0001) if slomo else None
    sendByte(256-(checksum&0xff))
    #print()
    return length

def transmitFile(src, dest):
    val = length = blocksize = 0
    try:
        fd = open(src,'rb')
    except FileNotFoundError:
        print(f"File not found: {src}")
        exit(1)
    # No needto do some seek around the file in python to determine the size
    length = os.path.getsize(src)
    if (length == -1 or length > 32 * 2**20):
        print(f"Skipping {src}")
        return
    transmitInit[7] = length & 0xff
    transmitInit[8] = (length >> 8) & 0xff
    transmitInit[9] = (length >> 16) & 0xff
    transmitInit[10] = (length >> 24) & 0xff
    for i in range(min(len(dest), MAX_FILENAME_LEN)):
        transmitInit[11+i] = bytes(dest[i],'utf-8')[0]
    sendBlock(transmitInit, len(transmitInit))
    receiveBlock(controlData, CONTROL_BUFSIZE)

    if controlData[0] == 0x10:
        print(f"Invalid destination file! src:{src} dest:{dest}")
        exit(1)

    if controlData[0] == 0x20:
        print("File exists on Portfolio",end='')
        if (force):
            print(" and is being overwritten!")
            sendBlock(transmitOverwrite,len(transmitOverwrite))
        else:
            print("! Use -fd to force overwriting.")
            sendBlock(transmitCancel, len(transmitCancel))
            return

    blocksize = controlData[1] | (controlData[2] << 8)
    if blocksize > PAYLOAD_BUFSIZE:
        print("Payload Buffer too small")
        exit(1)

    cb = (length+blocksize-1)/blocksize
    if length > blocksize:
        print(f"Transmission consists of {cb} blocks of payload.")
    ci = 0
    while length > blocksize:
        print(f"Transmitting Block {ci:03d}/{ci:03d}", end='') if verbose else None
        payload[:blocksize] = fd.read(blocksize)
        sendBlock(payload, blocksize)
        length -= blocksize
        ci += 1
    if length > 0:
        payload[:length] = fd.read(length)
        sendBlock(payload, length)
    receiveBlock(controlData, CONTROL_BUFSIZE)
    fd.close()

    if controlData[0] != 0x20:
        print(f"ERR{controlData[0]:02x}:Transmission failed!\nDisk Full or target directory not existant?")
        exit(1)

def receiveFile(source, dest):
    global sourcecount
    global nReceivedFiles
    fd = None
    i = num = length = total = 0
    destIsDir = 0
    blocksize = 0x7000
    startdir = bytearray(256)
    namebase = bytearray(MAX_FILENAME_LEN)
    basename = bytearray(MAX_FILENAME_LEN)
    pos = bytearray(MAX_FILENAME_LEN)

    #startdir[0:len(os.getcwd())] = bytearray(os.getcwd(), 'utf-8')
    startdir = os.getcwd()

    if os.path.isdir(dest):
        os.chdir(dest)
        destIsDir = 1

    for i in range(min(len(source),MAX_FILENAME_LEN)):
        receiveInit[i+3] = bytes(source[i],'utf-8')
    receiveInit[i+4] = 0 if i < MAX_FILENAME_LEN else None
    sendBlock(receiveInit, len(receiveInit))
    receiveBlock(listbuf, LIST_BUFSIZE)

    num = listbuf[0] | (listbuf[1] << 8)

    if num == 0:
        print(f"File not found on Portfolio: {source}")
        exit(1)
    """
    namebase[0:len(source)] = bytearray(source,'utf-8')
    pos = namebase.rfind(b':')
    if pos > -1:
        namebase = namebase[pos+1:]
    pos = namebase.rfind(b'\\')
    if pos > -1:
        namebase = namebase[pos+1:]
    """
    pos = receiveInit.rfind(b':')
    if pos > -1:
        pos += 1
    else:
        pos = 3
    pos = receiveInit[pos:].rfind(b'\\') + pos
    if pos > -1:
        pos += 1
    else:
        pos = 3

    basename[0:len(listbuf)-2] = listbuf[2:]
    basenames = [x for x in basename.split(b'\x00') if x != b'']

    if num != len(basenames):
        print("Something went wrong in my brain!")
        exit(1)

    for i in range(1,num+1):
        print(f"Transferring file {nReceivedFiles+1}", end='')
        if sourcecount == 1:
            print(f" of {num}", end='')
        print(f": {str(basenames[i-1], 'utf-8')}")

        if destIsDir:
            dest = basenames[i-1]

        if os.path.exists(dest):
            if not force:
                print("File exists! Use -f to force overwriting.")
                if i < num:
                    print("Remaining files are not copied!")
                exit(1)
                
        try:
            fd = open(dest, "wb")
        except Exception as e:
            print(f"{e}: Cannot create file: {dest.encode('utf-8')}")
            if i<num:
                print("Remaining files are not copied!")
                exit(1)

        receiveInit[0] = 2

        for ci in range(pos,min(len(basenames[i-1]),len(receiveInit))):
            receiveInit[pos+c] = basenames[i-1][ci]
        sendBlock(receiveInit, len(receiveInit))
        receiveBlock(controlData, CONTROL_BUFSIZE)

        if controlData[0] != 0x20:
            print("Unkown protocol error!")
            exit(1)

        total = controlData[7] | (controlData[8] << 8) | (controlData[9] << 16)

        if total > blocksize:
            nb = (total+blocksize-1)/blocksize
            print(f"Transmission onsits of {nb} blocks of payload")

        while total > 0:
            length = receiveBlock(payload, PAYLOAD_BUFSIZE)
            fd.write(payload)
            total -= length

        sendBlock(receiveFinish, len(receiveFinish))
        fd.close()

    if destIsdir:
        os.chdir(startdir)

    nReceivedFiles += num


def listFiles(pattern):
    i = num = 0
    global names, name        
    name = ""
    global payload 
    payload = bytearray(60000)
    if (len(pattern) > 82-3):
        print(f"Search Pattern too long! (maxlength : 79, pattern:{len(pattern)})")
        exit(1)
    print(f"Sending List files request for pattern {pattern}")
    for i in range(len(pattern)):
        receiveInit[i+3] = bytes(pattern[i],'utf-8')[0]
    sendBlock(receiveInit,82)
    receiveBlock(payload, 60000)

    num = (payload[1] << 8) | payload[0]
    if num == 0:
        print("No Files found")
        return
    names = list()
    for i in range(60000-2):
        name += chr(payload[i+2]) if payload[i+2] != 0 else ""
        if payload[i+2] == 0:
            names += [name] if name != '' else []
            name = ""
    print(f"Found {len(names)} Files.")
    print("\n".join(names))

def composePofoName(source, dest, pofoName, sourcecount):
    pos = ext = 0
    lastchar = ''

    dest = dest.replace('/','\\')

    pofoName = dest

    lastChar = pofoName[-1]
    if sourcecount > 1 or lastChar == '\\' or lastChar == ':':
        length = 0

        if lastChar != '\\':
            pofoName += '\\'

        pos = source.rfind('/')
        if not pos > -1:
            pos = source.rfind('\\')
        if pos > -1:
            pos += 1

        ext = source.rfind('.')
        if ext > -1:
            source = source.replace('.','_')

            length = ext - pos
            if length > 8:
                length = 8

            if length > MAX_FILENAME_LEN-len(pofoName):
                length = MAX_FILENAME_LEN-len(pofoName)
                pofoName = source[pos:pos+length]
                length = 4
                if length > MAX_FILENAME_LEN-len(pofoName):
                    length = MAX_FILENAME_LEN-len(pofoName)
                pofoName = source[ext:ext+length]
        else:
            length = 8
            if length > MAX_FILENAME_LEN-len(pofoName):
                length = MAX_FILENAME_LEN-len(pofoName)
            pofoName = source[ext:ext+length]

    print(f"after composePofo source:{source} dest:{dest} pofoName:{pofoName}") if verbose else None
    return pofoName


if __name__ == '__main__':
    mode = ''
    dest = None
    #listFiles('c:\\*.*')
    print("pytrans.py 0.01 - (c) 2022 by Carsten Busse")
    for i in range(1,len(sys.argv)):
        if sys.argv[i][0] == '-' or sys.argv[i][0] == '/':
            optLen = len(sys.argv[i])
            if optLen < 2 or optLen > 3:
                mode = 'h'
                break
            if mode !='':
                raise Exception("Only one Option of -r, -t, -l and -h can be selected per run!")
            for j in range(1,optLen):
                letter = sys.argv[i][j]
                letter = sys.argv[i][j].lower() if not letter in 'VD' else letter
                if letter in 'trl':
                    mode = letter
                    break
                elif letter == 'f':
                    force = 1
                    break
                elif letter == 'd':
                    device = None
                    break
                elif letter == 'v':
                    verbose += 1
                    break
                elif letter == 'V':
                    verbose += 2                    
                    break
                elif letter == 'D':
                    debug = True
                    break
                else:
                    mode = 'h'
                break
        else:
            if device is None:
                device = sys.argv[i]
            elif not sourcelist:
                print("Creating sourcelist")
                sourcelist = list()
                sourcelist.append(sys.argv[i])
                sourcecount = 1
                continue
            else:
                if dest or mode == 'l':
                    sourcecount +=1
            if i == len(sys.argv)-1:
                dest = sys.argv[i]
            else:
                print("Adding to sourcelist")
                sourcelist.append(sys.argv[i])
                sourcecount += 1

    if mode == 'h' or (mode == 't' and dest is None) or (mode == 'r' and dest is None) or (mode == 'l' and sourcelist is None):
           print(f"""
Syntax: {sys.argv[0]}
    [-d DEVICE]  for example \\.\LPT1  [autodetect]
    [-f]         Force overwrite [off]
    [-t|-r]      SOURCE DEST
or      {sys.argv[0]}
    [-l PATTERN]

    -d  Device to usb2lpt Parallel Port Device, Default value is "autodetect"
    -t  Transmit files(s) to Portfolio.
        Wildcards are not directly supported but may be expanded
        by the shell to generate a list of source files.
    -r  Receive file(s) from Portfolio.
        Wildcards in SOURCE are evaluated by the Portfolio.
        In a Unix like shell, quoting is required.
    -l  List directory files on Portfolio matchin PATTERN
    -f  Force overwriting an existing file.

Notes:
   SOURCE may be a single file or a list of files.
   In the latter case, DEST specifies a directory.
   The Portfolio must be in server mode when running this program!

   This program requires the usb2lpt hardware described on
   https://www-user.tu-chemnitz.de/~heha/basteln/PC/USB2LPT/
   this adapter will be accessed through windows ioctl's.""")
           exit(1)
    if type(device) is str:
        myport = usb2lpt.usb2lpt(device)
    else:
        myport = usb2lpt.usb2lpt()
    print("Waiting for Portfolio...")
    myport.outData(2)
    waitClockHigh()
    byte = receiveByte()
    while byte != 0x50:
        waitClockLow()
        myport.outData(0)
        waitClockHigh()
        myport.outData(2)
        byte = receiveByte()
    
    for i in range(sourcecount):
        if mode == 't':
            pofoName = ''
            pofoName = composePofoName(sourcelist[i], dest, pofoName, sourcecount)
            print(f"Transmitting file {i+1} of {sourcecount}: {sourcelist[i]} -> {pofoName}")
            transmitFile(sourcelist[i], pofoName)
        elif mode == 'r':
            receiveFile(sourcelist[i], dest)
        elif mode == 'l':
            listFiles(sourcelist[i])

    print("TASKS Finished.")
