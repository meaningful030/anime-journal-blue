import argparse
import threading
import webbrowser
from pathlib import Path

from waitress import serve
from journal import create_app, ROOT
from journal.export import export_public

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='啟動僅供本機使用的動漫手札')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    app = create_app()
    if not (ROOT / 'site' / 'index.html').is_file():
        export_public(app)
    print('公開頁面預覽：http://127.0.0.1:8000/\n本機站主管理：http://127.0.0.1:8000/login\n按 Ctrl+C 停止。', flush=True)
    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:8000/'))
        timer.daemon = True
        timer.start()
    serve(app, host='127.0.0.1', port=8000, threads=4, max_request_body_size=65536, clear_untrusted_proxy_headers=True)
