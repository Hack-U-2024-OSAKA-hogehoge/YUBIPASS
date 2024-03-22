import time

import serial

from .getImage import deviceid


def send_pass(send_pass,port):
    portNum = deviceid()
    baudRate = 115200
    
    try:
        # port = serial.Serial(portNum, baudRate, timeout=0.1,
        #                      inter_byte_timeout=0.1)
        # print("Port open success")
        # time.sleep(2)
        
        port.write(send_pass.encode())
        print("Pass sent")
        
    except Exception as e:
        print('Port open failed:', e)
        return False
    finally:
        port.close()