import base64, json, urllib.request, sys

TOKEN = "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"
REPO  = "shiraishi0101work/ai-blog-guide"
PATH  = "index.html"
FILE  = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\docs\guide\index.html"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/json",
}

# Get current SHA
url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    sha = json.loads(r.read())["sha"]

# Read and encode file
with open(FILE, "rb") as f:
    content = base64.b64encode(f.read()).decode()

# Upload
payload = json.dumps({
    "message": "feat: split sections into basic / option groups",
    "content": content,
    "sha": sha,
}).encode()

req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
with urllib.request.urlopen(req2) as r:
    result = json.loads(r.read())
    print("OK:", result["content"]["html_url"])
