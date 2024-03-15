from django.http import HttpResponse
from django.shortcuts import render

from .getImage import getFingerprintImage


def capture_fingerprint():
    # port_num = "COM5"  # 任意のポート番号に置き換える
    # baud_rate = 115200  # 任意のボーレートに置き換える
    # output_file_name = "print.bmp"  # 任意の出力ファイル名に置き換える
    
    # print("Capturing fingerprint...")
    
    getFingerprintImage()
    
    # if success:
    #     print ("Fingerprint captured and saved successfully!")
    #     return HttpResponse("Fingerprint captured and saved successfully!")
    # else:
    #     print ("Failed to capture fingerprint.")
    #     return HttpResponse("Failed to capture fingerprint.")
