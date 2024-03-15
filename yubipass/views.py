from django.http import HttpResponse
from django.shortcuts import render
# Create your views here.
from django.views.generic import TemplateView

# from .getImage import main
from .utils import capture_fingerprint


class IndexView(TemplateView):
    template_name = 'index.html'
    
    
class buttonView(TemplateView):
    template_name = 'button.html'
    def get(self, request, *args, **kwargs):
        # GETリクエストが来た時にデータ処理関数を呼び出す
        capture_fingerprint()
        return HttpResponse("Fingerprint captured and saved successfully!")