"""
Captive portal for HotBox setup.

Creates a WiFi AP named "HotBox-Setup", runs a DNS server (redirects
everything to 192.168.4.1) and an HTTP server that serves a config form.

Usage:
    from portal import run_portal
    config = run_portal()   # blocks until WiFi connects successfully
    # WiFi STA is connected when this returns; config is ready to save.
"""

import select
import socket
import time

import network

AP_SSID = "HotBox-Setup"
AP_IP = "192.168.4.1"

# OS captive-portal detection probes — redirect these to trigger the
# "Sign in to network" popup on iOS / Android / Windows.
_CAPTIVE_HOSTS = {
    "captive.apple.com",
    "connectivitycheck.gstatic.com",
    "clients3.google.com",
    "connectivitycheck.android.com",
    "www.msftconnecttest.com",
    "www.msftncsi.com",
    "detectportal.firefox.com",
}

# ── HTML templates ────────────────────────────────────────────────────────────

_PAGE = """\
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HotBox Setup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f0f0f0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.wrap{width:100%;max-width:400px;padding:16px}
h1{font-size:1.4rem;margin-bottom:2px}
.sub{color:#888;font-size:.88rem;margin-bottom:18px}
.card{background:#fff;border-radius:14px;padding:22px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.err{background:#fff0f0;border:1px solid #fcc;border-radius:8px;padding:11px 14px;margin-bottom:16px;color:#c00;font-size:.9rem}
label{display:block;font-size:.82rem;font-weight:700;color:#555;margin-top:16px;margin-bottom:5px;text-transform:uppercase;letter-spacing:.03em}
input,select{width:100%;padding:11px 13px;border:1.5px solid #ddd;border-radius:9px;font-size:1rem;outline:none;background:#fafafa;transition:border .15s}
input:focus,select:focus{border-color:#e55;background:#fff}
#hrs{margin-top:16px}
.btn{display:block;width:100%;margin-top:22px;padding:14px;background:#e55;color:#fff;border:none;border-radius:9px;font-size:1.05rem;font-weight:700;cursor:pointer;letter-spacing:.02em}
.btn:hover{background:#c44}
</style>
</head>
<body>
<div class="wrap">
<h1>&#127777;&#65039; HotBox Setup</h1>
<p class="sub">Configure WiFi and test duration</p>
%%ERR%%
<div class="card">
<form method="POST" action="/configure">
<label>WiFi Network</label>
<input name="ssid" type="text" placeholder="Network name" value="%%SSID%%" autocomplete="off" spellcheck="false" required>
<label>WiFi Password</label>
<input name="password" type="password" placeholder="Leave blank for open networks" autocomplete="off">
<label>Nopal API Token</label>
<input name="api_token" type="password" placeholder="Leave blank to skip Nopal sync" autocomplete="off" spellcheck="false">
<label>Nopal Project (optional)</label>
<input name="project" type="text" placeholder="Leave blank for Personal" value="%%PROJECT%%" autocomplete="off" spellcheck="false">
<label>Test Duration</label>
<select name="dtype" onchange="document.getElementById('hrs').style.display=this.value==='hours'?'block':'none'">
<option value="indefinite"%%INDEF%%>Run indefinitely</option>
<option value="hours"%%HSEL%%>Fixed duration (hours)</option>
</select>
<div id="hrs" style="display:%%HDISP%%">
<label>Hours</label>
<input name="hours" type="number" min="1" max="720" value="%%HRS%%" placeholder="24">
</div>
<button class="btn" type="submit">Start Test &#8594;</button>
</form>
</div>
</div>
</body>
</html>"""

_WAIT = """\
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connecting&#8230;</title>
<style>body{font-family:system-ui,sans-serif;max-width:400px;margin:60px auto;padding:0 20px;text-align:center}</style>
</head>
<body>
<h2>&#9203; Connecting&#8230;</h2>
<p style="margin-top:12px">Connecting to <strong>%%SSID%%</strong>.</p>
<p style="color:#666;font-size:.9rem;margin-top:10px">&#127777;&#65039; %%NOPAL%%</p>
<p style="color:#888;font-size:.9rem;margin-top:16px">
If nothing happens within 20 seconds,<br>
reconnect to <b>HotBox-Setup</b> and try again.
</p>
</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _render(error="", ssid="", project="", dtype="indefinite", hours=24):
    err_html = f'<div class="err">{error}</div>' if error else ""
    page = _PAGE.replace("%%ERR%%", err_html)
    page = page.replace("%%SSID%%", ssid)
    page = page.replace("%%PROJECT%%", project)
    page = page.replace("%%INDEF%%", " selected" if dtype != "hours" else "")
    page = page.replace("%%HSEL%%", " selected" if dtype == "hours" else "")
    page = page.replace("%%HDISP%%", "block" if dtype == "hours" else "none")
    page = page.replace("%%HRS%%", str(hours))
    return page


def _render_wait(ssid, api_token, project):
    if api_token:
        nopal = f"Nopal sync: enabled &#8594; {project if project else 'Personal'}"
    else:
        nopal = "Nopal sync: disabled (no token entered)"
    return _WAIT.replace("%%SSID%%", ssid).replace("%%NOPAL%%", nopal)


def _urldecode(s):
    s = s.replace("+", " ")
    out = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            out.append(chr(int(s[i + 1 : i + 3], 16)))
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _parse_form(body):
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[_urldecode(k)] = _urldecode(v)
    return params


def _dns_response(data):
    """Return a DNS A-record response pointing all queries to AP_IP."""
    try:
        ip = bytes(int(x) for x in AP_IP.split("."))
        # Header: TX ID | flags QR+RA | QDCOUNT | ANCOUNT | NSCOUNT | ARCOUNT
        header = (
            data[:2]
            + b"\x81\x80"
            + data[4:6]
            + data[4:6]  # echo QDCOUNT as ANCOUNT
            + b"\x00\x00\x00\x00"
        )
        # Echo the full question section, then append the answer
        answer = (
            b"\xc0\x0c"  # name pointer → offset 12
            + b"\x00\x01\x00\x01"  # type A, class IN
            + b"\x00\x00\x00\x3c"  # TTL 60s
            + b"\x00\x04"  # RDLENGTH = 4
            + ip
        )
        return header + data[12:] + answer
    except Exception:
        return b""


def _http_send(conn, status, body, ctype="text/html"):
    if isinstance(body, str):
        body = body.encode()
    conn.sendall(
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {ctype}; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n".encode()
        + body
    )


def _http_redirect(conn, location):
    body = b""
    conn.sendall(
        f"HTTP/1.1 302 Found\r\n"
        f"Location: http://{AP_IP}{location}\r\n"
        "Content-Length: 0\r\n"
        "Connection: close\r\n\r\n".encode()
    )


def _read_request(conn):
    """Read a full HTTP request (header + body)."""
    conn.settimeout(4)
    raw = b""
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            raw += chunk
            if b"\r\n\r\n" in raw:
                hdr_end = raw.index(b"\r\n\r\n") + 4
                hdr = raw[:hdr_end].decode("utf-8", "ignore")
                cl = 0
                for line in hdr.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        try:
                            cl = int(line.split(":", 1)[1].strip())
                        except Exception:
                            pass
                if len(raw) - hdr_end >= cl:
                    break
    except OSError:
        pass
    return raw.decode("utf-8", "ignore")


def _parse_request(req):
    """Return (method, path, host, body)."""
    lines = req.split("\r\n")
    parts = lines[0].split(" ") if lines else []
    method = parts[0] if parts else "GET"
    path = parts[1].split("?")[0] if len(parts) > 1 else "/"
    host = ""
    for line in lines[1:]:
        if line.lower().startswith("host:"):
            host = line.split(":", 1)[1].strip().split(":")[0]
            break
    body = req.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in req else ""
    return method, path, host, body


# ── Portal sockets ────────────────────────────────────────────────────────────


def _make_dns():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 53))
    return s


def _make_http():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(4)
    return s


# ── Main entry point ──────────────────────────────────────────────────────────


def run_portal(error=""):
    """
    Start the captive portal AP and serve the config form.
    Blocks until the user provides valid WiFi credentials that connect.

    Returns a raw config dict:
        {"wifi_ssid", "wifi_password", "api_token", "project",
         "indefinite", "duration_hours"}

    "api_token"/"project" are None when left blank — a blank token means
    Nopal sync is skipped entirely (see vault.py); a blank project means
    the caller's Personal space.

    WiFi STA is connected (not yet disconnected) when this returns.
    """
    ap = network.WLAN(network.AP_IF)
    ap.config(ssid=AP_SSID, security=0)
    ap.active(True)
    while not ap.active():
        time.sleep(0.1)
    ap.ifconfig((AP_IP, "255.255.255.0", AP_IP, AP_IP))
    print(f"Portal: AP '{AP_SSID}' up at {AP_IP}")

    dns_sock = _make_dns()
    http_sock = _make_http()

    poller = select.poll()
    poller.register(dns_sock, select.POLLIN)
    poller.register(http_sock, select.POLLIN)

    form = {"ssid": "", "project": "", "dtype": "indefinite", "hours": 24}

    try:
        while True:
            for sock, _ in poller.poll(50):
                # ── DNS ───────────────────────────────────────────────────────
                if sock is dns_sock:
                    try:
                        data, addr = dns_sock.recvfrom(512)
                        resp = _dns_response(data)
                        if resp:
                            dns_sock.sendto(resp, addr)
                    except OSError:
                        pass

                # ── HTTP ──────────────────────────────────────────────────────
                elif sock is http_sock:
                    try:
                        conn, _ = http_sock.accept()
                    except OSError:
                        continue

                    try:
                        req = _read_request(conn)
                        method, path, host, body = _parse_request(req)

                        # Captive portal detection probes → redirect to trigger OS popup
                        if host in _CAPTIVE_HOSTS:
                            _http_redirect(conn, "/")
                            conn.close()
                            continue

                        if method == "POST" and path == "/configure":
                            p = _parse_form(body)
                            ssid = p.get("ssid", "").strip()
                            password = p.get("password", "")
                            api_token = p.get("api_token", "").strip()
                            project = p.get("project", "").strip()
                            dtype = p.get("dtype", "indefinite")
                            hours_raw = p.get("hours", "24")
                            form = {
                                "ssid": ssid,
                                "project": project,
                                "dtype": dtype,
                                "hours": hours_raw,
                            }

                            if not ssid:
                                _http_send(
                                    conn,
                                    "200 OK",
                                    _render(
                                        "WiFi network name cannot be empty.", **form
                                    ),
                                )
                                conn.close()
                                continue

                            # Serve "connecting" page immediately
                            _http_send(
                                conn, "200 OK", _render_wait(ssid, api_token, project)
                            )
                            conn.close()

                            # Tear down portal to attempt STA connection
                            poller.unregister(dns_sock)
                            poller.unregister(http_sock)
                            dns_sock.close()
                            http_sock.close()
                            ap.active(False)

                            # Try connecting as STA
                            sta = network.WLAN(network.STA_IF)
                            sta.active(True)
                            sta.connect(ssid, password)
                            connected = False
                            for _ in range(20):
                                if sta.isconnected():
                                    connected = True
                                    break
                                time.sleep(0.5)

                            if connected:
                                try:
                                    hours = int(hours_raw)
                                except Exception:
                                    hours = 24
                                return {
                                    "wifi_ssid": ssid,
                                    "wifi_password": password,
                                    "api_token": api_token or None,
                                    "project": project or None,
                                    "indefinite": dtype != "hours",
                                    "duration_hours": hours if dtype == "hours" else 0,
                                }

                            # Connection failed — restart portal with error
                            sta.active(False)
                            error = f'Could not connect to "{ssid}". Check the name and password and try again.'

                            ap.config(ssid=AP_SSID, security=0)
                            ap.active(True)
                            while not ap.active():
                                time.sleep(0.1)
                            ap.ifconfig((AP_IP, "255.255.255.0", AP_IP, AP_IP))

                            dns_sock = _make_dns()
                            http_sock = _make_http()
                            poller.register(dns_sock, select.POLLIN)
                            poller.register(http_sock, select.POLLIN)

                        elif path in ("/", "/index.html"):
                            _http_send(conn, "200 OK", _render(error, **form))
                            conn.close()
                            error = ""

                        else:
                            _http_redirect(conn, "/")
                            conn.close()

                    except Exception as e:
                        print(f"Portal HTTP error: {e}")
                        try:
                            conn.close()
                        except Exception:
                            pass

    finally:
        try:
            dns_sock.close()
        except Exception:
            pass
        try:
            http_sock.close()
        except Exception:
            pass
        try:
            ap.active(False)
        except Exception:
            pass
