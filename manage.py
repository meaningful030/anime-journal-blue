import argparse
import getpass
import zipfile
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

from journal import create_app
from journal.db import connect
from journal.export import export_public
from journal.images import import_image


def main():
    parser = argparse.ArgumentParser(description='動漫手札的本機管理工具')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-owner', help='建立或重設唯一站主；密碼不會顯示')
    sub.add_parser('export', help='產生 public/ 公開網站，不會自動上傳')
    sub.add_parser('backup', help='將資料庫與圖片備份至 instance/backups/')
    image = sub.add_parser('import-image', help='從本機匯入一張公開用照片，取代此作品的原照片')
    image.add_argument('entry_id', type=int)
    image.add_argument('path')
    image.add_argument('--alt', required=True, help='會公開的圖片文字說明')
    image.add_argument('--public-image', action='store_true', required=True, help='確認這是準備公開的圖片')
    args = parser.parse_args()
    app = create_app()
    if args.command == 'init-owner':
        with connect(app.config['DATABASE']) as db:
            if db.execute('SELECT 1 FROM owner').fetchone():
                if input('將重設唯一站主並登出所有裝置。輸入 RESET 確認：') != 'RESET':
                    return
            username = input('站主帳號（3–60 字）：').strip()
            password = getpass.getpass('密碼（至少 14 字，可用長句）：')
            confirmation = getpass.getpass('再輸入一次密碼：')
            if not 3 <= len(username) <= 60 or not 14 <= len(password) <= 256 or password != confirmation:
                parser.error('帳號或密碼長度不符，或兩次密碼不同。')
            db.execute('INSERT INTO owner VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,password_hash=excluded.password_hash', (username, generate_password_hash(password, method='scrypt')))
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM login_attempts')
        print('站主設定完成。請在 http://127.0.0.1:8000/login 登入。')
    elif args.command == 'export':
        print(f'已匯出 {export_public(app)} 部作品到 public/，尚未上傳。')
    elif args.command == 'import-image':
        try:
            import_image(app, args.entry_id, args.path, args.alt)
        except ValueError as e:
            parser.error(str(e))
        print('已匯入並移除圖片中繼資料。請檢查照片畫面，再產生公開網站。')
    elif args.command == 'backup':
        folder = Path(app.config['DATA_DIR']) / 'backups'
        folder.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        snapshot = folder / (stamp + '.sqlite3')
        with connect(app.config['DATABASE']) as source, connect(snapshot) as dest:
            source.backup(dest)
            dest.execute('DELETE FROM sessions')
            dest.execute('DELETE FROM login_attempts')
        archive = folder / (stamp + '.zip')
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot, 'journal.sqlite3')
            for photo in (Path(app.config['DATA_DIR']) / 'photos').glob('*.jpg'):
                z.write(photo, 'photos/' + photo.name)
        snapshot.unlink()
        print(f'私人備份：{archive}\n含密碼雜湊與私人草稿，請勿上傳 GitHub。')


if __name__ == '__main__':
    main()
