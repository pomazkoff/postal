#!/usr/bin/env python3
"""Set Privacy + Support URLs once GitHub Pages is live. Does NOT submit for review."""
import os,time,jwt,requests
KID='DSDD69RDV3'; ISS='dd386e9b-c44a-4fde-b3b1-7e93fff5a273'
BASE='https://api.appstoreconnect.apple.com'
PRIVACY='https://pomazkoff.github.io/POSTAL/privacy.html'
SUPPORT='https://pomazkoff.github.io/POSTAL/support.html'
LOC='adfecd6d-ba0d-4dd0-b82e-a8be821577ed'
def token():
    now=int(time.time())
    return jwt.encode({'iss':ISS,'iat':now,'exp':now+1100,'aud':'appstoreconnect-v1'},os.environ['ASC_API_KEY_P8'],algorithm='ES256',headers={'kid':KID,'typ':'JWT'})
# verify URLs
for u in (PRIVACY,SUPPORT):
    r=requests.get(u,timeout=30); print(u, r.status_code, r.headers.get('content-type'))
    if r.status_code!=200: raise SystemExit('URL not live')
r=requests.patch(BASE+f'/v1/appStoreVersionLocalizations/{LOC}',
  headers={'Authorization':'Bearer '+token(),'Content-Type':'application/json'},
  json={'data':{'type':'appStoreVersionLocalizations','id':LOC,'attributes':{'privacyPolicyUrl':PRIVACY,'supportUrl':SUPPORT}}}, timeout=60)
print('PATCH', r.status_code, r.text[:300])
