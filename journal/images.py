import secrets
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .db import connect


def import_image(app, entry_id, source, alt):
    source = Path(source)
    if not source.is_file() or source.stat().st_size > 12 * 1024 * 1024:
        raise ValueError('請選擇 12 MiB 以內的 JPEG、PNG 或 WebP 圖片。')
    if not 1 <= len(alt.strip()) <= 200:
        raise ValueError('圖片說明需為 1–200 字，匯出時會公開。')
    with connect(app.config['DATABASE']) as db:
        if not db.execute('SELECT 1 FROM entries WHERE id=?', (entry_id,)).fetchone():
            raise ValueError('找不到作品編號，請先在管理頁新增作品。')
    name = secrets.token_hex(16) + '.jpg'
    output = Path(app.config['DATA_DIR']) / 'photos' / name
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(source) as image:
                if image.format not in {'JPEG','PNG','WEBP'} or image.width * image.height > 24_000_000:
                    raise ValueError('圖片格式不支援，或超過 2,400 萬像素。')
                image.load()
                oriented = ImageOps.exif_transpose(image)
                oriented.thumbnail((1800,1800))
                # Copy pixels to a fresh image: EXIF, GPS, comments and profiles
                # are intentionally not passed through to the public JPEG.
                rgba = oriented.convert('RGBA')
                clean = Image.new('RGB', rgba.size, '#faf7ef')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                clean.save(output, format='JPEG', quality=86, optimize=True)
        with connect(app.config['DATABASE']) as db:
            db.execute('INSERT INTO photos(entry_id,filename,alt) VALUES (?,?,?) ON CONFLICT(entry_id) DO UPDATE SET filename=excluded.filename,alt=excluded.alt', (entry_id, name, alt.strip()))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as e:
        output.unlink(missing_ok=True)
        raise ValueError('圖片無法安全讀取，請換一張圖片。') from e
    return name
