# PyInstaller yapılandırma dosyası.
# Windows EXE üretmek için bu dosya Windows'ta derlenmelidir: pyinstaller muhasebe_asistani.spec
#
# ONEDIR MODU: Çıktı tek bir .exe değil, dist/MuhasebeAsistani/ altında bir
# klasördür (.exe + tüm bağımlılıklar). Kurumsal/kilitli PC'lerde admin
# yetkisi olmadan çalıştırmak için bu mod tercih edilir: onefile modunun
# aksine her açılışta %TEMP%'e kendi kendine açılmaz (bazı AppLocker/antivirüs
# politikaları %TEMP%'ten çalıştırmayı engelliyor, ayrıca her seferinde açılış
# yavaşlıyordu). Dağıtım için dist/MuhasebeAsistani klasörünü zip'leyip
# kullanıcının Masaüstü/Belgeler gibi yazılabilir bir yere çıkarması yeterli.

block_cipher = None

hiddenimports = ["xlrd", "xlwt"]

# pywin32 kuruluysa bütün gerekli COM alt modüllerini paketle. Kurulu değilse
# EXE yine derlenir ve uygulama Windows PowerShell COM yedeğini kullanır.
try:
    from PyInstaller.utils.hooks import collect_submodules

    hiddenimports += collect_submodules("win32com")
    hiddenimports += ["pythoncom", "pywintypes"]
except Exception:
    pass

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("config", "config"),
        ("assets", "assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["app/runtime_hook_qt.py"],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# exclude_binaries=True + aşağıdaki COLLECT() adımı onedir modunu oluşturur.
# Bu ikisi olmadan (eski haliyle) tek dosyalık onefile EXE üretilirdi.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MuhasebeAsistani",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/carpan.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MuhasebeAsistani",
)
