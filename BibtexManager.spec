# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Force-collect packages that PyInstaller misses
bibtexparser_datas, bibtexparser_binaries, bibtexparser_hiddenimports = collect_all('bibtexparser')
unidecode_datas, unidecode_binaries, unidecode_hiddenimports = collect_all('unidecode')
httpx_datas, httpx_binaries, httpx_hiddenimports = collect_all('httpx')
httpcore_datas, httpcore_binaries, httpcore_hiddenimports = collect_all('httpcore')
certifi_datas, certifi_binaries, certifi_hiddenimports = collect_all('certifi')

all_datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('data', 'data'),
    ('schema.sql', '.'),
] + bibtexparser_datas + unidecode_datas + httpx_datas + httpcore_datas + certifi_datas

all_binaries = bibtexparser_binaries + unidecode_binaries + httpx_binaries + httpcore_binaries + certifi_binaries

all_hiddenimports = [
    'bibtexparser',
    'bibtexparser.bparser',
    'bibtexparser.bwriter',
    'bibtexparser.bibdatabase',
    'bibtexparser.customization',
    'bibtexparser.latexenc',
    'Levenshtein',
    'unidecode',
    'httpx',
    'httpx._transports',
    'httpx._transports.default',
    'httpcore',
    'httpcore._backends',
    'httpcore._backends.sync',
    'h11',
    'certifi',
    'pyparsing',
    'flask',
    'flask.json',
    'jinja2',
    'markupsafe',
    'werkzeug',
    'click',
    'itsdangerous',
    'blinker',
    'sqlite3',
] + bibtexparser_hiddenimports + unidecode_hiddenimports + httpx_hiddenimports + httpcore_hiddenimports + certifi_hiddenimports

excludes = [
    'scholarly',
    'selenium',
    'trio',
    'PyQt5',
    'tkinter',
    'matplotlib',
    'numpy',
    'PIL',
    'IPython',
    'notebook',
    'sphinx',
    'docutils',
    'babel',
    'pytest',
    'black',
    'yapf_third_party',
]

a = Analysis(
    ['app.py'],
    pathex=['/Users/ozzychen/Desktop/bibtex-manager'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BibtexManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='BibtexManager',
)

app = BUNDLE(
    coll,
    name='BibtexManager.app',
    bundle_identifier='com.ozzychen.bibtexmanager',
    info_plist={
        'CFBundleName': 'BibTeX Manager',
        'CFBundleDisplayName': 'BibTeX Manager',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    },
)
