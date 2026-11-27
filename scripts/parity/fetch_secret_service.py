import urllib.request,lzma,pathlib,subprocess
root=pathlib.Path('.tmp/secret-service');(root/'packages').mkdir(parents=True,exist_ok=True);base='https://deb.debian.org/debian/'
data=lzma.decompress(urllib.request.urlopen(base+'dists/trixie/main/binary-arm64/Packages.xz').read()).decode()
packages={}
for block in data.split('\n\n'):
 fields=dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
 if 'Package' in fields:packages[fields['Package']]=fields
for name in ['dbus-daemon','dbus-bin','dbus-session-bus-common','gnome-keyring','libsecret-1-0','libgck-1-0','libgcr-base-3-1','libgcrypt20','libcap-ng0','libdbus-1-3','libgpg-error0','libapparmor1']:
 p=packages[name];file=root/'packages'/pathlib.Path(p['Filename']).name
 urllib.request.urlretrieve(base+p['Filename'],file);subprocess.run(['dpkg-deb','-x',str(file),str(root/'root')],check=True);print(name,file,flush=True)
