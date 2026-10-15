import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import SecurityError

from .db import connect, initialize
from .dates import category, taipei_today, premiere_bounds

ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    app = Flask(__name__, instance_path=str(ROOT / 'instance'))
    app.config.update(
        DATA_DIR=str(ROOT / 'instance'),
        SECRET_KEY=None,
        SESSION_COOKIE_NAME='anime_local_session',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=False,  # This manager is loopback HTTP only, never hosted.
        SESSION_REFRESH_EACH_REQUEST=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_TIME_LIMIT=3600,
        MAX_CONTENT_LENGTH=65536,
        MAX_FORM_MEMORY_SIZE=65536,
        MAX_FORM_PARTS=30,
        TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'],
    )
    if config:
        app.config.update(config)
    data = Path(app.config['DATA_DIR']).resolve()
    data.mkdir(parents=True, exist_ok=True)
    (data / 'photos').mkdir(exist_ok=True)
    if not app.config['SECRET_KEY']:
        key = data / 'session.key'
        try:
            with key.open('x', encoding='ascii') as f:
                f.write(secrets.token_hex(32))
            key.chmod(0o600)
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = key.read_text(encoding='ascii').strip()
    app.config['DATABASE'] = str(data / 'journal.sqlite3')
    initialize(app.config['DATABASE'])
    dummy_hash = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')

    def db():
        if 'db' not in g:
            g.db = connect(app.config['DATABASE'], close_on_exit=False)
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        if 'db' in g:
            g.db.close()

    @app.before_request
    def local_only():
        # Host validation plus peer validation protects the local manager from LAN
        # exposure and DNS rebinding. Never trust forwarded headers here.
        if request.remote_addr not in {'127.0.0.1', '::1'}:
            abort(403)
        g.owner = False
        token = session.get('auth')
        if isinstance(token, str):
            g.owner = bool(db().execute(
                'SELECT 1 FROM sessions WHERE token_hash=? AND expires>?',
                (hashlib.sha256(token.encode()).hexdigest(), int(time.time())),
            ).fetchone())

    CSRFProtect(app)

    def owner_required(fn):
        @wraps(fn)
        def guarded(*args, **kwargs):
            if not g.owner:
                if request.method != 'GET':
                    abort(403)
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return guarded

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def home():
        return redirect(url_for('preview', filename='index.html'))

    @app.get('/preview/<path:filename>')
    def preview(filename):
        return send_from_directory(ROOT / 'public', filename)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.owner:
            return redirect(url_for('admin'))
        owner = db().execute('SELECT * FROM owner WHERE id=1').fetchone()
        error, status = None, 200
        if request.method == 'POST':
            now = int(time.time())
            address = hmac.new(app.secret_key.encode(), request.remote_addr.encode(), 'sha256').hexdigest()
            with db():
                db().execute('DELETE FROM login_attempts WHERE window_start <= ?', (now - 900,))
                db().execute('DELETE FROM sessions WHERE expires <= ?', (now,))
                db().execute('INSERT INTO login_attempts VALUES (?, 1, ?) ON CONFLICT(address_hash) DO UPDATE SET count=count+1', (address, now))
                attempt = db().execute('SELECT count FROM login_attempts WHERE address_hash=?', (address,)).fetchone()['count']
            if attempt > 5:
                error, status = '嘗試次數過多，請於 15 分鐘後再試。', 429
            else:
                username = request.form.get('username', '')[:100]
                password = request.form.get('password', '')
                matched = check_password_hash(owner['password_hash'] if owner else dummy_hash, password[:256])
                if owner and len(password) <= 256 and matched and hmac.compare_digest(username.encode(), owner['username'].encode()):
                    token = secrets.token_urlsafe(32)
                    with db():
                        db().execute('INSERT INTO sessions VALUES (?,?)', (hashlib.sha256(token.encode()).hexdigest(), now + 8*3600))
                        db().execute('DELETE FROM login_attempts WHERE address_hash=?', (address,))
                    session.clear()
                    session.permanent = True
                    session['auth'] = token
                    return redirect(url_for('admin'))
                error, status = '帳號或密碼不正確。', 401
        return render_template('login.html', has_owner=bool(owner), error=error), status

    @app.post('/logout')
    @owner_required
    def logout():
        with db():
            db().execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(session['auth'].encode()).hexdigest(),))
        session.clear()
        return redirect(url_for('login'))

    @app.get('/admin')
    @owner_required
    def admin():
        entries = db().execute('SELECT e.*, p.id AS photo_id FROM entries e LEFT JOIN photos p ON p.entry_id=e.id ORDER BY e.id DESC').fetchall()
        return render_template('admin.html', entries=entries, category=category, today=taipei_today())

    @app.route('/admin/new', methods=['GET', 'POST'])
    @app.route('/admin/<int:entry_id>/edit', methods=['GET', 'POST'])
    @owner_required
    def edit(entry_id=None):
        entry = db().execute('SELECT * FROM entries WHERE id=?', (entry_id,)).fetchone() if entry_id else None
        if entry_id and not entry:
            abort(404)
        values = dict(entry) if entry else {'title':'', 'premiere':'', 'note':'', 'published':0}
        error = None
        if request.method == 'POST':
            values = {k: request.form.get(k, '').strip() for k in ['title','premiere','note']}
            values['published'] = int(request.form.get('published') == '1')
            if not 1 <= len(values['title']) <= 120 or len(values['note']) > 10000:
                error = '標題需要 1–120 字，心得最多 10,000 字。'
            if values['premiere']:
                try:
                    premiere_bounds(values['premiere'])
                except ValueError:
                    error = '請填 YYYY-MM 或 YYYY-MM-DD；未知時請留空。'
            if not error:
                args = (values['title'], values['premiere'] or None, values['note'], values['published'])
                with db():
                    if entry_id:
                        db().execute('UPDATE entries SET title=?,premiere=?,note=?,published=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (*args, entry_id))
                    else:
                        db().execute('INSERT INTO entries(title,premiere,note,published) VALUES (?,?,?,?)', args)
                flash('已儲存在本機。確認內容後，按「產生公開網站」更新預覽。')
                return redirect(url_for('admin'))
        photo = db().execute('SELECT * FROM photos WHERE entry_id=?', (entry_id,)).fetchone() if entry_id else None
        return render_template('edit.html', entry=values, entry_id=entry_id, error=error, photo=photo), 400 if error else 200

    @app.route('/admin/<int:entry_id>/delete', methods=['GET','POST'])
    @owner_required
    def delete(entry_id):
        entry = db().execute('SELECT * FROM entries WHERE id=?', (entry_id,)).fetchone()
        if not entry:
            abort(404)
        if request.method == 'POST':
            # Orphan files stay private, allowing a backup before manual cleanup.
            with db():
                db().execute('DELETE FROM entries WHERE id=?', (entry_id,))
            flash('已從本機刪除。重新產生並發布網站後，公開頁面才會更新。')
            return redirect(url_for('admin'))
        return render_template('delete.html', entry=entry)

    @app.get('/admin/photo/<int:photo_id>')
    @owner_required
    def photo(photo_id):
        photo = db().execute('SELECT filename FROM photos WHERE id=?', (photo_id,)).fetchone()
        if not photo:
            abort(404)
        return send_from_directory(data / 'photos', photo['filename'])

    @app.post('/admin/export')
    @owner_required
    def export():
        from .export import export_public
        count = export_public(app)
        flash(f'已產生 {count} 部作品的公開網站，可先開啟預覽；尚未傳送到 GitHub。')
        return redirect(url_for('admin'))

    @app.errorhandler(CSRFError)
    def csrf_error(_):
        return render_template('error.html', message='表單已過期或驗證失敗，請重新開啟頁面再試。'), 400

    @app.errorhandler(SecurityError)
    def invalid_host(_):
        # Invalid hosts have no URL adapter, so do not render url_for links.
        return 'Invalid local host.', 400, {'Content-Type':'text/plain; charset=utf-8'}

    for status in [400,403,404,413,500]:
        def error_page(error):
            return render_template('error.html', message={400:'這個請求無法處理。',403:'無法存取，請先在本機登入。',404:'找不到這個頁面。',413:'內容過大，請縮短後重試。',500:'暫時無法完成，請查看本機終端機。'}.get(error.code,'無法完成請求。')), error.code
        app.register_error_handler(status, error_page)
    return app
