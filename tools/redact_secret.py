import os

secrets = {
    'p&rPnV4Bz@VAn7guMKQEOw&wMX@JF6': 'REDACTED_QBITTORRENT_PASSWORD'
}

files_to_check = [
    'old-flask-app/config.py'
]

for f in files_to_check:
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                s = fh.read()
            original = s
            for k, v in secrets.items():
                s = s.replace(k, v)
            if s != original:
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(s)
        except Exception:
            pass
