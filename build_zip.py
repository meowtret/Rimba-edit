"""Kemas folder rimba_edit menjadi ZIP siap dipasang di QGIS.

Pemakaian:  python build_zip.py
Hasil:      dist/rimba_edit-<versi>.zip
"""
import configparser
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PLUGIN = 'rimba_edit'

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, PLUGIN, 'metadata.txt'), encoding='utf-8')
version = cfg['general']['version']

os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
out = os.path.join(ROOT, 'dist', '{}-{}.zip'.format(PLUGIN, version))
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
    for folder, dirs, files in os.walk(os.path.join(ROOT, PLUGIN)):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for name in files:
            if name.endswith('.pyc'):
                continue
            path = os.path.join(folder, name)
            zf.write(path, os.path.relpath(path, ROOT))
print(out)
