"""
Entry point for the SACA Android app.

The phone runs the unchanged SACA Flask app inside its WebView with Pyodide (Python compiled to WebAssembly).
There is no web server: boot.js turns every link and form into a call to handle(), which passes it to Flask's
test client and returns the page. Data lives in /data, which boot.js keeps in the WebView's IndexedDB.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SACA_DATA_DIR", "/data")
os.environ["SACA_PORTABLE"] = "1"  # use dataset_v2/saca_v2_model.json, no scikit-learn on the phone
for path in (os.path.join(HERE, "vendor"), HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
os.makedirs(os.environ["SACA_DATA_DIR"], exist_ok=True)


# Pyodide's Python is built without OpenSSL, so hashlib has no pbkdf2_hmac. Werkzeug needs it for password and
# PIN hashes, so add the standard algorithm (RFC 8018) built on hashlib's own SHA-256. Same output as OpenSSL.
import hashlib  # noqa: E402

if not hasattr(hashlib, "pbkdf2_hmac"):
    _TRANS_36 = bytes((x ^ 0x36) for x in range(256))
    _TRANS_5C = bytes((x ^ 0x5C) for x in range(256))

    def _pbkdf2_hmac(hash_name, password, salt, iterations, dklen=None):
        inner, outer = hashlib.new(hash_name), hashlib.new(hash_name)
        block = inner.block_size
        if len(password) > block:
            password = hashlib.new(hash_name, password).digest()
        password = password + b"\x00" * (block - len(password))
        inner.update(password.translate(_TRANS_36))
        outer.update(password.translate(_TRANS_5C))

        def prf(msg):
            i, o = inner.copy(), outer.copy()
            i.update(msg)
            o.update(i.digest())
            return o.digest()

        dklen = dklen or outer.digest_size
        out, n = b"", 1
        while len(out) < dklen:
            u = prf(salt + n.to_bytes(4, "big"))
            acc = int.from_bytes(u, "big")
            for _ in range(iterations - 1):
                u = prf(u)
                acc ^= int.from_bytes(u, "big")
            out += acc.to_bytes(len(u), "big")
            n += 1
        return out[:dklen]

    hashlib.pbkdf2_hmac = _pbkdf2_hmac

_spec = importlib.util.spec_from_file_location("saca_app_entry", os.path.join(HERE, "logistic_regression.app.py"))
_entry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_entry)

from classifier.pipeline import SACAPipeline  # noqa: E402

_pipeline = SACAPipeline(extractor=None)  # offline: no LLM extractor
_pipeline.classifier.train()              # loads the portable model
app = _entry.create_app(pipeline=_pipeline, config={"VOICE_AVAILABLE": False})
client = app.test_client()


def handle(method, url, body="", content_type=""):
    """Run one request. Returns [status, final_url, mimetype, text]. Redirects are followed."""
    kwargs = {}
    if method.upper() == "POST":
        kwargs = {"data": body or "", "content_type": content_type or "application/x-www-form-urlencoded"}
    response = client.open(url, method=method.upper(), follow_redirects=True, **kwargs)
    req = response.request
    final = req.path + (("?" + req.query_string.decode()) if req.query_string else "")
    mimetype = response.mimetype or ""
    if mimetype.startswith("text/") or mimetype in ("application/json", "application/javascript"):
        text = response.get_data(as_text=True)
    else:
        text = ""
    return [response.status_code, final, mimetype, text]
