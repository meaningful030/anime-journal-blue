"""Remove expired rich content from the deployment artifact, without private data.

Runs in GitHub Actions with Python's standard library only. Git history and
third-party caches are not erased; only the newly served artifact is reduced.
"""
import json
import hashlib
import re
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PREFIX = 'window.JOURNAL_ENTRIES = '


def refresh(folder, today=None):
    folder = Path(folder).resolve()
    today = today or datetime.now(ZoneInfo('Asia/Taipei')).date()
    n = today.year * 12 + today.month - 7
    year, month = divmod(n, 12)
    month += 1
    cutoff = date(year, month, min(today.day, monthrange(year, month)[1]))
    path = folder / 'entries.js'
    script = path.read_text(encoding='utf-8')
    if not script.startswith(PREFIX):
        raise ValueError('Unrecognized public data format')
    entries = json.loads(script[len(PREFIX):].strip().removesuffix(';'))
    output, keep = [], set()
    for entry in entries:
        premiere = date.fromisoformat(entry['premiere'])
        if premiere > today:
            continue
        safe = {key:entry[key] for key in ['id','title','premiere']}
        if premiere >= cutoff:
            safe['note'] = entry.get('note','')
            image = entry.get('image','')
            if re.fullmatch(r'images/[a-f0-9]{32}\.jpg',image):
                safe.update(image=image, alt=entry.get('alt',''))
                keep.add(Path(image).name)
        output.append(safe)
    encoded = json.dumps(output,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    path.write_text(PREFIX + encoded + ';\n', encoding='utf-8')
    index = folder / 'index.html'
    html = index.read_text(encoding='utf-8')
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    html = re.sub(r'\./entries\.js(?:\?v=[a-f0-9]+)?"', f'./entries.js?v={version}"', html)
    index.write_text(html, encoding='utf-8')
    image_dir = folder / 'images'
    if image_dir.is_symlink():
        raise ValueError('Symlink images directory is not allowed')
    for image in image_dir.glob('*.jpg'):
        if image.name not in keep:
            image.unlink()
    return len(output)


if __name__ == '__main__':
    print(f'Refreshed {refresh(Path(__file__).parent / "public")} public entries.')
