"""Download every District 6 tree-basin photo from the SF 311 Verint portal.

Resumable: already-downloaded case ids are skipped, so it can be re-run safely.
"""
import json, re, base64, io, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
import requests
from PIL import Image, ImageOps

OUT = "/tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad/d6img"
BASE = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

cases = json.load(open("/home/user/fairtrees/public/data/snapshot.json"))["cases"]
targets = [c for c in cases if c["d"] == "6" and c["p"] and c["p"].startswith("v:")]
print(f"district 6 photo cases: {len(targets)}", flush=True)


def fetch(case):
    cid = case["id"]
    dest = os.path.join(OUT, f"{cid}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return ("skip", cid)

    caseid, formref = case["p"][2:].split(":")
    try:
        s = requests.Session()
        h = {"User-Agent": UA, "Referer": "https://mobile311.sfgov.org/"}
        wrapper = f"{BASE}/form/auto/download_attachments?caseid={caseid}&formref={formref}"
        r = s.get(wrapper, headers=h, timeout=20)
        if r.status_code != 200:
            return ("fail", cid, f"wrapper {r.status_code}")
        m = re.search(r'name="_csrf_token"\s+content="([^"]+)"', r.text)
        h2 = {"User-Agent": UA, "Referer": wrapper, "Origin": BASE,
              "Content-Type": "application/json"}
        if m:
            h2["X-CSRF-TOKEN"] = m.group(1)
        hs = s.get(f"{BASE}/api/citizen?archived=Y&preview=false&locale=en", headers=h2, timeout=20)
        if "Authorization" in hs.headers:
            h2["Authorization"] = hs.headers["Authorization"]

        body = lambda extra=None: {
            "data": {"caseid": caseid, "formref": formref, **(extra or {})},
            "name": "download_attachments", "email": "", "xref": "", "xref1": "", "xref2": "",
        }
        rl = s.post(f"{BASE}/api/custom?action=get_attachments_details&actionedby=&loadform=true"
                    f"&access=citizen&locale=en", json=body(), headers=h2, timeout=20)
        if rl.status_code != 200:
            return ("fail", cid, f"list {rl.status_code}")
        names = (rl.json().get("data") or {}).get("formdata_filenames", "")
        target = None
        for n in names.split(";"):
            n = n.strip(); low = n.lower()
            if not n or re.search(r"(m\.jpg|_map\.jpe?g)$", low):
                continue
            if low.endswith((".jpg", ".jpeg", ".png")):
                target = n; break
        if not target:
            return ("fail", cid, "no image attachment")

        ri = s.post(f"{BASE}/api/custom?action=download_attachment&actionedby=&loadform=true"
                    f"&access=citizen&locale=en", json=body({"filename": target}), headers=h2, timeout=40)
        if ri.status_code != 200:
            return ("fail", cid, f"download {ri.status_code}")
        b64 = ((ri.json().get("data") or {}).get("txt_file") or "")
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        raw = base64.b64decode(b64)
        if len(raw) < 1000:
            return ("fail", cid, "empty")

        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)          # honour camera rotation
        img = img.convert("RGB")
        img.thumbnail((1000, 1000), Image.LANCZOS)  # plenty for print at ~2.5in wide
        img.save(dest, "JPEG", quality=78, optimize=True)
        return ("ok", cid)
    except Exception as e:
        return ("fail", cid, f"{type(e).__name__}: {str(e)[:60]}")


t0 = time.time()
ok = skip = fail = 0
fails = []
with ThreadPoolExecutor(max_workers=4) as pool:
    for i, res in enumerate(pool.map(fetch, targets), 1):
        if res[0] == "ok": ok += 1
        elif res[0] == "skip": skip += 1
        else:
            fail += 1; fails.append(res[1:])
        if i % 25 == 0 or i == len(targets):
            print(f"  {i}/{len(targets)}  ok={ok} skip={skip} fail={fail}  {time.time()-t0:.0f}s", flush=True)

print(f"\nDONE ok={ok} skip={skip} fail={fail} in {time.time()-t0:.0f}s", flush=True)
if fails:
    print("failures:", flush=True)
    for f in fails[:25]:
        print("  ", f, flush=True)
json.dump([f[0] for f in fails], open(os.path.join(OUT, "_failures.json"), "w"))
