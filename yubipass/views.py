from django.http import HttpResponse
from django.shortcuts import redirect, render
# Create your views here.
from django.views.generic import TemplateView

# from .getImage import main
from .utils import capture_fingerprint


class IndexView(TemplateView):
    template_name = 'index.html'
    
    
class buttonView(TemplateView):
    def post(self, request, *args, **kwargs):
        # POSTリクエストが来た時にデータ処理関数を呼び出す
        text_data = request.POST.get('inputData', '')  # 'text_data'はフォームのinputタグのname属性の値です
        print(text_data)
        capture_fingerprint(text_data)
        return redirect('http://localhost:8000')  # リダイレクト先のURLを指定