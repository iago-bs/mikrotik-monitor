from PyInstaller.utils.hooks import collect_all, collect_submodules

# Coletar todos os submódulos de dns e eventlet
datas, binaries, hiddenimports = collect_all('dns')
datas2, binaries2, hiddenimports2 = collect_all('eventlet')

datas += datas2
binaries += binaries2
hiddenimports += hiddenimports2
