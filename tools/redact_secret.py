import os

secrets = {
    # Do NOT commit actual secrets here. Replace the placeholder with the real value
    # before using an external filtering tool if needed.
    'QBITTORRENT_PASSWORD_PLACEHOLDER': 'REDACTED_QBITTORRENT_PASSWORD'
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
