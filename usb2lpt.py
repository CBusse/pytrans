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

import ctypes
import ctypes.wintypes as wintypes
import pyioctl
import time


verbose = 1

debug = False

slomo = False

class usb2lptException(Exception):
    pass

class usb2lpt:
    ioctls = {
            'IOCTL_VLPT_XramRead':0x22228E,
            'IOCTL_VLPT_OutIn'   :0x222010,
            }

    def __init__(self,_dev='autodetect'):
        posDevs = [
            r'\\.\LPT1',
            r'\\.\LPT2',
            r'\\.\LPT3',
            r'\\.\LPT4',
            ]
        if _dev=='autodetect':
            # use first available interface
            found = False
            for tdev in posDevs:
                print(f"Trying to open {tdev}") if debug else None
                res = self._open(tdev)
                if res:
                    self.dev  = tdev
                    found = True
                    break
            if not found:
                raise usb2lptException("No valid usb2lpt device found!")
        else:
            res = self._open(_dev)
            if res:
                self.dev = _dev
            else:
                raise usb2lptException("No valid usb2lpt device found!")

        print(f"Device {self.dev} initialised and ready for ioctls (Firmware:{self.firmware})") if verbose else None

    def _open(self,dev):
        self.dctl = pyioctl.DeviceIoControl(dev)
        try:
            self.dctl.__enter__()
        except pyioctl.DeviceIoControlException:
            return False
        else:
            return self._verifyDevice()

        return self

    def _Dosdatetime_to_filetime(self,date):
        """
https://learn.microsoft.com/de-de/windows/win32/api/winbase/nf-winbase-dosdatetimetofiletime            
0-4 Day of the month (1–31)
5-8 Month (1 = January, 2 = February, and so on)
9-15    Year offset from 1980 (add 1980 to get actual year)
        """
        dval = date
        day = dval & 0x1f            #5 bits
        dval = dval >> 5
        month = dval & 0xf           #4 nits
        dval = dval >> 4
        year = 1980 + (dval & 0x3f)  #6 bits, from 2044 on we got a problem
        return (day, month, year)

    def _verifyDevice(self):
        addr = wintypes.WORD(6)
        p_addr = ctypes.pointer(addr)
        date = wintypes.WORD()
        p_date = ctypes.pointer(date)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_XramRead'],
                                       p_addr, ctypes.sizeof(wintypes.WORD),
                                       p_date, ctypes.sizeof(wintypes.WORD))
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            #print(f"Last_Error {lErr}/ENUM {strErr.args[0]} '{strErr.args[1]}'")
            ctypes.set_last_error(0)
            raise usb2lptException(f"Last_Error {lErr}/ENUM {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if status:
                day, month, year = self._Dosdatetime_to_filetime(date.value)
                self.firmware=f"{day:02d}.{month:02d}.{year:4d}"
                # we got successfully to this point, so we are assured that this device is in place
                return True
            else:
                return False

    def directIO(self):
        # not sure if this is needed for Portfolio
        print("Switching device to directIO Mode") if verbose else None
        self.dctl._validate()
        barr = 2 * ctypes.c_ubyte
        sdmode = barr(15,1 << 6)   # bit 6 st or set value 6= mmh
        p_sdmode = ctypes.pointer(sdmode)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_sdmode,ctypes.sizeof(ctypes.c_byte)*2,
                                           None,0)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")

    def inData(self):
        #self.dctl._validate()
        b = ctypes.c_ubyte(0x10)   # read data port
        p_b = ctypes.pointer(b)
        rv = ctypes.c_ubyte(0)
        p_rv = ctypes.pointer(rv)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_b,ctypes.sizeof(ctypes.c_byte),
                                           p_rv,ctypes.sizeof(ctypes.c_byte))
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if status:
                return rv.value
            else:
                raise usb2lptException("Could not gather Value from Data port!")

    def inStatus(self):
        #self.dctl._validate()
        b = ctypes.c_ubyte(0x11)  #  read status port
        p_b = ctypes.pointer(b)
        rv = ctypes.c_ubyte(0)
        p_rv = ctypes.pointer(rv)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_b,ctypes.sizeof(ctypes.c_byte),
                                           p_rv,ctypes.sizeof(ctypes.c_byte))
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if status:
                return rv.value
            else:
                raise usb2lptException("Could not gather Value from Status port!")

    def inControl(self):
        #self.dctl._validate()
        b = ctypes.c_ubyte(0x12)  #  read Control port
        p_b = ctypes.pointer(b)
        rv = ctypes.c_ubyte(0)
        p_rv = ctypes.pointer(rv)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_b,ctypes.sizeof(ctypes.c_byte),
                                           p_rv,ctypes.sizeof(ctypes.c_byte))
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if status:
                return rv.value
            else:
                raise usb2lptException("Could not gather Value from Dataport!")

    def inTriple(self):
        #self.dctl._validate()
        barr = 3 * ctypes.c_ubyte
        selp = barr(0x10,0x11,0x12) # read from data, status and control port
        p_selp = ctypes.pointer(selp)
        rp = barr(0,0,0)
        p_rp = ctypes.pointer(rp)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_selp,ctypes.sizeof(ctypes.c_ubyte)*3,
                                           p_rp,ctypes.sizeof(ctypes.c_ubyte)*3)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if status:
                return (rp[0], rp[1], rp[2])
            else:
                raise usb2lptException("Could not gather Values from Device!")

    def outData(self, data):
        #self.dctl._validate()
        barr = 2 * ctypes.c_ubyte
        oarr = barr(0,data)
        p_oarr = ctypes.pointer(oarr)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_oarr,ctypes.sizeof(ctypes.c_ubyte)*2,
                                           None, 0)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if not status:
                raise usb2lptException("Could not output Value to Data Port!")


    def outStatus(self, data):
        self.dctl._validate()
        barr = 2 * ctypes.c_ubyte
        oarr = barr(1,data)
        p_oarr = ctypes.pointer(oarr)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_oarr,ctypes.sizeof(ctypes.c_ubyte)*2,
                                           None, 0)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if not status:
                raise usb2lptException("Could not output Value to Status Port!")

    def outControl(self, data):
        self.dctl._validate()
        barr = 2 * ctypes.c_ubyte
        oarr = barr(2,data)
        p_oarr = ctypes.pointer(oarr)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_oarr,ctypes.sizeof(ctypes.c_byte)*2,
                                           None, 0)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if not status:
                raise usb2lptException("Could not output Value to Control Port!")

    def outTriple(self, darr):
        self.dctl._validate()
        barr = 6 * ctypes.c_ubyte
        oarr = barr(0,darr[0],1,darr[1],2,darr[2])
        p_oarr = ctypes.pointer(oarr)
        try:
            status, junk = self.dctl.ioctl(self.ioctls['IOCTL_VLPT_OutIn'],
                                           p_oarr,ctypes.sizeof(ctypes.c_byte)*2,
                                           None, 0)
        except pyioctl.DeviceIoControlException:
            lErr = ctypes.get_last_error()
            strErr = ctypes.WinError(lErr)
            raise usb2lptException(f"IO Error {strErr.args[0]} '{strErr.args[1]}'")
        else:
            if not status:
                raise usb2lptException("Could not output Values to Device!")



   


if __name__ == '__main__':
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
    receiveInit = bytearray(82)  # maxsize is 62
    receiveInit[0] = 0x06
    receiveInit[1] = 0x00
    receiveInit[2] = 0x70
    #receiveInit[3:6] = b'C:\\'

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
        print()
        return length

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

    myport = usb2lpt()
    listFiles('c:\\*.*')

