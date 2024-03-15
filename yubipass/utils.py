from django.http import HttpResponse
from django.shortcuts import render

from .getImage import getFingerprintImage
from .hash import get_hash
from .send_pass import send_pass


def capture_fingerprint(url):
    getFingerprintImage()
    pass_hash=get_hash(url)
    send_pass(pass_hash)
