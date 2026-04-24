"""
auth.py の OAuth認証方式を修正するパッチスクリプト
実行: sudo python3 /opt/unpaid_check/patch_auth.py
"""
import re

path = "/opt/unpaid_check/auth.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_refresh = '''def _refresh(service_name: str, token_data: dict, company_id: str = "") -> dict:
    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })'''

new_refresh = '''def _refresh(service_name: str, token_data: dict, company_id: str = "") -> dict:
    svc  = _svc(service_name)
    resp = requests.post(svc["token_url"], data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id":     svc["client_id"],
        "client_secret": svc["client_secret"],
    })'''

old_callback = '''    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":   "authorization_code",
        "code":          code,
        "redirect_uri":  svc["redirect_uri"],
    })'''

new_callback = '''    svc  = _svc(service_name)
    resp = requests.post(svc["token_url"], data={
        "grant_type":    "authorization_code",
        "code":           code,
        "redirect_uri":   svc["redirect_uri"],
        "client_id":      svc["client_id"],
        "client_secret":  svc["client_secret"],
    })'''

if old_refresh not in content:
    print("ERROR: _refresh function not found. Already patched?")
elif old_callback not in content:
    print("ERROR: handle_callback function not found. Already patched?")
else:
    content = content.replace(old_refresh, new_refresh)
    content = content.replace(old_callback, new_callback)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: auth.py patched. Please run: sudo systemctl restart unpaid_check")
