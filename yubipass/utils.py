from django.http import HttpResponse
from django.shortcuts import render

from .getImage import getFingerprintImage
from .hash import get_hash


def capture_fingerprint(url):
    getFingerprintImage()
    get_hash(url)
