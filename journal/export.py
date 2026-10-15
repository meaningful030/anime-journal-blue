import json
import re
import shutil
import tempfile
from pathlib import Path

from .db import connect
from .dates import category, taipei_today

DATA_PREFIX = 'window.JOURNAL_ENTRIES = '


def export_public(app, today=None, root=None):
    """Export only an explicit public allowlist. Never copy the database."""
    root = Path(root or app.root_path).resolve()
    if root.name == 'journal' and root == Path(app.root_path).resolve():
        root = root.parent
    today = today or taipei_today()
    output = root / 'public'
    data_dir = Path(app.config['DATA_DIR']).resolve()
    if output.is_symlink() or (output.exists() and not (output / '.generated').is_file()):
        raise RuntimeError('public 必須是程式產生的目錄；請先保留現有檔案。')
    entries = []
    with connect(app.config['DATABASE']) as db:
        rows = db.execute('SELECT e.*,p.filename,p.alt FROM entries e LEFT JOIN photos p ON p.entry_id=e.id WHERE e.published=1 ORDER BY e.premiere DESC,e.id DESC').fetchall()
    staging = Path(tempfile.mkdtemp(prefix='export-', dir=data_dir)).resolve()
    try:
        (staging / '.generated').write_text('Generated public website only.\n', encoding='utf-8')
        (staging / '.nojekyll').touch()
        for name in ['index.html','style.css','app.js','favicon.svg']:
            shutil.copyfile(Path(app.root_path) / 'static' / name, staging / name)
        (staging / 'images').mkdir()
        for row in rows:
            group = category(row['premiere'], today)
            if group == 'pending':
                continue
            item = {'id':row['id'], 'title':row['title'], 'premiere':row['premiere']}
            if group == 'recent':
                item['note'] = row['note']
                if row['filename']:
                    name = row['filename']
                    if not re.fullmatch(r'[a-f0-9]{32}\.jpg', name):
                        raise ValueError('圖片名稱不合法。')
                    source = data_dir / 'photos' / name
                    if source.is_symlink():
                        raise ValueError('圖片不能是符號連結。')
                    shutil.copyfile(source, staging / 'images' / name)
                    item['image'] = 'images/' + name
                    item['alt'] = row['alt']
            entries.append(item)
        payload = json.dumps(entries, ensure_ascii=True, separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        (staging / 'entries.js').write_text(DATA_PREFIX + payload + ';\n', encoding='utf-8')
        # All recursive cleanup stays in this application's fixed generated paths.
        previous = data_dir / 'previous-export'
        if previous.exists():
            if previous.is_symlink() or not (previous / '.generated').is_file():
                raise RuntimeError('無法安全清理舊匯出。')
            shutil.rmtree(previous)
        if output.exists():
            output.rename(previous)
        try:
            staging.rename(output)
        except OSError:
            if previous.exists():
                previous.rename(output)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        return len(entries)
    finally:
        if staging.exists() and staging.parent == data_dir and staging.name.startswith('export-'):
            shutil.rmtree(staging)
