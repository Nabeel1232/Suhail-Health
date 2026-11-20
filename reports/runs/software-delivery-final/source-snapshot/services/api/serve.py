"""Container entry point; seed only an explicitly enabled synthetic demo."""
import os
import uvicorn
from .config import settings
from .db import init_db

def main():
    init_db()
    if settings()['demo_mode']:
        from .seed import seed
        seed()
    uvicorn.run('services.api.main:app',host='0.0.0.0',port=int(os.environ.get('PORT','8000')))

if __name__=='__main__':main()
