# error_middleware.py

from django.shortcuts import redirect


class ErrorRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # 500エラーの場合、リダイレクトする
        if response.status_code == 500:
            return redirect('index')  # エラーページのURLに変更する
        return response
