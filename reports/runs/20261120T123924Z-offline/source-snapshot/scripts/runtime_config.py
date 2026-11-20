"""Generate application credentials separately from owner's unmodified environment."""
import os,secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'.runtime/app.env'
p.parent.mkdir(exist_ok=True)
if not p.exists():
 pw=secrets.token_urlsafe(32)
 p.write_text('DATABASE_URL=postgresql+psycopg://suhail:'+pw+'@127.0.0.1:55432/suhail\nPOSTGRES_USER=suhail\nPOSTGRES_DB=suhail\nPOSTGRES_PASSWORD='+pw+'\nDEMO_MODE=true\nSESSION_SECURE=false\n')
 p.chmod(0o600)
print('Runtime configuration ready in ignored .runtime/app.env; owner dotenv unchanged.')
