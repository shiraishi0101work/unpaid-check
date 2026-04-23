import base64, json, urllib.request

TOKEN = "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"
REPO  = "shiraishi0101work/ai-blog-guide"
PATH  = "guide.pdf"
FILE  = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\06【AIブログマスター仕様説明書】\guide.pdf"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/json",
}

with open(FILE, "rb") as f:
    content = base64.b64encode(f.read()).decode()

url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
payload = json.dumps({
    "message": "add: guide PDF for download",
    "content": content,
}).encode()

req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())
    print("OK:", result["content"]["download_url"])
