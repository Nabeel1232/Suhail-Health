"""Reset only the API's explicitly identified synthetic demo-v1 dataset."""
import httpx
with httpx.Client(base_url='http://127.0.0.1:18000',timeout=30) as c:
    r=c.post('/auth/demo',json={'role':'admin'})
    if not r.is_success:raise SystemExit('Synthetic demonstration access is disabled or unavailable; no records changed.')
    r=c.post('/demo/reset')
    if not r.is_success:raise SystemExit('Demonstration reset rejected; no unrelated dataset was requested.')
print('Reset demo-v1 only; unrelated records preserved.')
