import hashlib
import json
import re
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

from journal import create_app
from journal.db import connect, initialize
from journal.dates import category, premiere_bounds, six_months_before, taipei_today
from journal.export import export_public, DATA_PREFIX
from journal.images import import_image
from refresh_public import refresh


class DateTests(unittest.TestCase):
    def test_calendar_month_end_and_leap_year(self):
        for now, expected in [('2026-10-15','2026-04-15'),('2026-08-31','2026-02-28'),('2024-08-31','2024-02-29'),('2026-03-31','2025-09-30'),('2026-01-01','2025-07-01')]:
            self.assertEqual(six_months_before(date.fromisoformat(now)).isoformat(),expected)

    def test_inclusive_boundary_and_pending(self):
        today = date(2026,10,15)
        for value, expected in [('2026-04-15','recent'),('2026-04-14','archive'),('2026-10-15','recent'),('2026-10-16','pending'),(None,'pending')]:
            self.assertEqual(category(value,today),expected)

    def test_taipei_timezone(self):
        with patch('journal.dates.datetime') as clock:
            clock.now.side_effect = lambda zone: datetime(2026,10,14,16,1,tzinfo=timezone.utc).astimezone(zone)
            self.assertEqual(taipei_today(),date(2026,10,15))

    def test_month_precision_and_uncertain_boundaries(self):
        today = date(2026,10,15)
        for value, expected in [('2012-04','archive'),('2026-03','archive'),('2026-04','pending'),('2026-05','recent'),('2026-10','pending'),('2026-11','pending')]:
            self.assertEqual(category(value,today),expected)
        self.assertEqual(category('2026-04',date(2026,10,1)),'recent')
        self.assertEqual(category('2026-10',date(2026,10,31)),'recent')
        self.assertEqual(premiere_bounds('2024-02'),(date(2024,2,1),date(2024,2,29)))
        for invalid in ['2026-1','2026-13','20261015','2026-W42-4']:
            with self.assertRaises(ValueError):
                premiere_bounds(invalid)


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'test-only-long-passphrase'
        cls.password_hash = generate_password_hash(cls.password, method='scrypt')

    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / 'instance' / 'test-runs'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.root = Path(self.temp.name)
        self.app = create_app({'TESTING':True,'SECRET_KEY':'test-only-session-key','DATA_DIR':str(self.root/'private')})
        self.client = self.app.test_client()
        with connect(self.app.config['DATABASE']) as db:
            db.execute('INSERT INTO owner VALUES (1,?,?)',('tester',self.password_hash))

    def tearDown(self):
        self.temp.cleanup()

    def csrf(self, path='/login', client=None):
        page = (client or self.client).get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"',page).group(1)

    def login(self):
        return self.client.post('/login',data={'csrf_token':self.csrf(),'username':'tester','password':self.password})

    def add(self,title='TEST ONLY',premiere='2026-10-01',note='test note',published=1):
        with connect(self.app.config['DATABASE']) as db:
            return db.execute('INSERT INTO entries(title,premiere,note,published) VALUES (?,?,?,?)',(title,premiere,note,published)).lastrowid

    def read_export(self):
        script = (self.root/'site'/'entries.js').read_text(encoding='utf-8')
        return json.loads(script[len(DATA_PREFIX):].strip().removesuffix(';'))

    def test_write_routes_require_auth_even_with_valid_csrf(self):
        entry = self.add()
        token = self.csrf()
        for path in ['/admin/new',f'/admin/{entry}/edit',f'/admin/{entry}/delete','/admin/export','/logout']:
            self.assertEqual(self.client.post(path,data={'csrf_token':token,'title':'UNAUTHORIZED'}).status_code,403)
        with connect(self.app.config['DATABASE']) as db:
            self.assertEqual(db.execute('SELECT title FROM entries').fetchone()[0],'TEST ONLY')

    def test_csrf_required_for_login_and_all_authenticated_writes(self):
        self.assertEqual(self.client.post('/login',data={'username':'tester','password':self.password}).status_code,400)
        self.login()
        for path in ['/admin/new','/admin/1/edit','/admin/1/delete','/admin/export','/logout']:
            self.assertEqual(self.client.post(path,data={'title':'NO TOKEN'}).status_code,400)

    def test_authenticated_create_update_delete(self):
        self.assertEqual(self.login().status_code,302)
        result = self.client.post('/admin/new',data={'csrf_token':self.csrf('/admin/new'),'title':'測試作品','premiere':'2026-10-15','note':'測試心得','published':'1'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(self.client.post('/admin/1/edit',data={'csrf_token':self.csrf('/admin/1/edit'),'title':'修改測試','premiere':'','note':'草稿'}).status_code,302)
        with connect(self.app.config['DATABASE']) as db:
            row = db.execute('SELECT * FROM entries').fetchone()
            self.assertEqual((row['title'],row['premiere'],row['published']),('修改測試',None,0))
        self.assertEqual(self.client.get('/admin/1/delete').status_code,200)
        self.assertEqual(self.client.post('/admin/1/delete',data={'csrf_token':self.csrf('/admin/1/delete')}).status_code,302)
        with connect(self.app.config['DATABASE']) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM entries').fetchone()[0],0)

    def test_xss_sql_injection_and_validation(self):
        self.login()
        malicious = '<script>alert(1)</script>\'; DROP TABLE entries; --'
        self.client.post('/admin/new',data={'csrf_token':self.csrf('/admin/new'),'title':malicious,'note':'<img src=x onerror=alert(1)>','premiere':'2026-10-01'})
        page = self.client.get('/admin').get_data(as_text=True)
        self.assertNotIn('<script>alert',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertEqual(self.client.post('/admin/new',data={'csrf_token':self.csrf('/admin/new'),'title':'t','premiere':'2026-02-30'}).status_code,400)
        self.assertEqual(self.client.post('/admin/new',data={'csrf_token':self.csrf('/admin/new'),'title':'x'*121}).status_code,400)

    def test_month_only_edit_export_and_scheduled_refresh(self):
        self.login()
        response = self.client.post('/admin/new',data={'csrf_token':self.csrf('/admin/new'),'title':'月份作品','premiere':'2012-04','note':'PRIVATE_OLD_NOTE','published':'1'})
        self.assertEqual(response.status_code,302)
        self.assertIn('value="2012-04"',self.client.get('/admin/1/edit').get_data(as_text=True))
        with connect(self.app.config['DATABASE']) as db:
            self.assertEqual(db.execute('SELECT premiere FROM entries').fetchone()[0],'2012-04')
        self.add('MONTH_RECENT','2026-05','recent note')
        self.add('MONTH_BOUNDARY','2026-04','uncertain')
        self.assertEqual(export_public(self.app,date(2026,10,15),self.root),2)
        self.assertEqual([row['title'] for row in self.read_export()],['MONTH_RECENT','月份作品'])
        self.assertNotIn('note',self.read_export()[1])
        self.assertEqual(refresh(self.root/'site',date(2026,10,15)),2)
        self.assertEqual(self.read_export()[1]['premiere'],'2012-04')
        self.assertEqual(refresh(self.root/'site',date(2026,12,1)),2)
        self.assertTrue(all('note' not in row for row in self.read_export()))

    def test_session_logout_revokes_replay(self):
        self.login()
        cookie = self.client.get_cookie('anime_local_session')
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.same_site,'Strict')
        replay = self.app.test_client()
        replay.set_cookie('anime_local_session',cookie.value)
        self.assertEqual(replay.get('/admin').status_code,200)
        self.client.post('/logout',data={'csrf_token':self.csrf('/admin')})
        self.assertEqual(replay.get('/admin').status_code,302)

    def test_session_expiry_is_checked_server_side(self):
        self.login()
        with connect(self.app.config['DATABASE']) as db:
            db.execute('UPDATE sessions SET expires=?',(int(time.time())-1,))
        self.assertEqual(self.client.get('/admin').status_code,302)

    def test_rate_limit_persists_across_clients(self):
        for _ in range(5):
            response = self.client.post('/login',data={'csrf_token':self.csrf(),'username':'tester','password':'wrong'})
            self.assertEqual(response.status_code,401)
        other = self.app.test_client()
        self.assertEqual(other.post('/login',data={'csrf_token':self.csrf(client=other),'username':'tester','password':self.password}).status_code,429)

    def test_local_only_host_and_security_headers(self):
        self.assertEqual(self.client.get('/login',environ_overrides={'REMOTE_ADDR':'192.168.1.2'}).status_code,403)
        self.assertEqual(self.client.get('/login',headers={'Host':'evil.example'}).status_code,400)
        response = self.client.get('/login')
        self.assertEqual(response.headers['X-Frame-Options'],'DENY')
        self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.get('/instance/session.key').status_code,404)
        self.assertEqual(self.client.get('/preview/../instance/journal.sqlite3').status_code,404)
        self.assertEqual(self.client.get('/register').status_code,404)
        self.assertNotIn('type="file"',response.get_data(as_text=True))

    def test_export_allowlist_and_no_private_leaks(self):
        self.add('RECENT','2026-04-15','public <script> text')
        self.add('ARCHIVE','2026-04-14','OLD_NOTE_SECRET')
        self.add('FUTURE_SECRET','2026-10-16','future')
        self.add('UNKNOWN_SECRET',None,'unknown')
        self.add('DRAFT_SECRET','2026-10-01','draft',0)
        self.assertEqual(export_public(self.app,date(2026,10,15),self.root),2)
        data = self.read_export()
        self.assertEqual(data[0]['title'],'RECENT')
        self.assertNotIn('note',data[1])
        all_text = ''.join(p.read_text(encoding='utf-8') for p in (self.root/'site').rglob('*') if p.is_file())
        for secret in ['FUTURE_SECRET','UNKNOWN_SECRET','DRAFT_SECRET','OLD_NOTE_SECRET',self.password_hash,self.app.secret_key]:
            self.assertNotIn(secret,all_text)
        self.assertFalse(list((self.root/'site').rglob('*.sqlite3')))
        self.assertNotIn('<script> text',all_text)

    def test_image_metadata_export_and_archive_pruning(self):
        entry = self.add(premiere='2026-04-15')
        image_path = self.root/'source.jpg'
        exif = Image.Exif()
        exif[270] = 'PRIVATE METADATA'
        Image.new('RGB',(2400,1200),'skyblue').save(image_path,exif=exif)
        name = import_image(self.app,entry,image_path,'公開測試圖','https://example.org/art/')
        with Image.open(Path(self.app.config['DATA_DIR'])/'photos'/name) as processed:
            self.assertFalse(processed.getexif())
            self.assertLessEqual(processed.width,1800)
        self.assertEqual(self.client.get('/admin/photo/1').status_code,302)
        export_public(self.app,date(2026,10,15),self.root)
        self.assertTrue((self.root/'site'/'images'/name).is_file())
        self.assertEqual(self.read_export()[0]['image_source'],'https://example.org/art/')
        refresh(self.root/'site',date(2026,10,15))
        self.assertEqual(self.read_export()[0]['image_source'],'https://example.org/art/')
        refresh(self.root/'site',date(2026,10,16))
        self.assertNotIn('note',self.read_export()[0])
        self.assertNotIn('image',self.read_export()[0])
        self.assertNotIn('image_source',self.read_export()[0])
        self.assertFalse((self.root/'site'/'images'/name).exists())

    def test_reexport_removes_unpublished_files(self):
        entry = self.add()
        export_public(self.app,date(2026,10,15),self.root)
        before = (self.root/'site'/'index.html').read_text(encoding='utf-8')
        with connect(self.app.config['DATABASE']) as db:
            db.execute('UPDATE entries SET published=0 WHERE id=?',(entry,))
        export_public(self.app,date(2026,10,15),self.root)
        self.assertEqual(self.read_export(),[])
        after = (self.root/'site'/'index.html').read_text(encoding='utf-8')
        self.assertNotEqual(before,after)
        self.assertRegex(after,r'entries\.js\?v=[a-f0-9]{12}')

    def test_preview_serves_current_export_directory(self):
        self.add('PREVIEW CHECK','2024-07')
        export_public(self.app,date(2026,10,16),self.root)
        with patch('journal.ROOT',self.root):
            response=self.client.get('/preview/index.html')
            self.assertEqual(response.status_code,200)
            response.close()
            data=self.client.get('/preview/entries.js')
            self.assertIn('PREVIEW CHECK',data.get_data(as_text=True))
            data.close()

    def test_invalid_image_rejected(self):
        entry = self.add()
        fake = self.root/'malicious.svg'
        fake.write_text('<svg><script>alert(1)</script></svg>')
        with self.assertRaises(ValueError):
            import_image(self.app,entry,fake,'test')
        for unsafe in ['javascript:alert(1)','https://example.org\\@evil.test/','https://user:secret@example.org/']:
            with self.assertRaisesRegex(ValueError,'HTTPS'):
                import_image(self.app,entry,fake,'test',unsafe)

    def test_existing_photo_migration_preserves_records(self):
        legacy = self.root/'legacy.sqlite3'
        with connect(legacy) as db:
            db.execute('CREATE TABLE photos (id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL UNIQUE, filename TEXT NOT NULL UNIQUE, alt TEXT NOT NULL)')
            db.execute('INSERT INTO photos VALUES (1,42,?,?)',('existing.jpg','Existing alt'))
        initialize(legacy)
        initialize(legacy)
        with connect(legacy) as db:
            row = db.execute('SELECT filename,alt,source_url FROM photos WHERE id=1').fetchone()
            self.assertEqual(tuple(row),('existing.jpg','Existing alt',''))


if __name__ == '__main__':
    unittest.main()
