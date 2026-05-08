"""
VOIDFLIX - Servidor com TMDB API
Roda em 0.0.0.0
"""

import http.server
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import threading
import webbrowser
import gzip
import ssl
import time

PORT = int(os.environ.get("PORT", 8765))  # Render define PORT via env var
FRONTEND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

TMDB_KEY  = "8265bd1679663a7ea12ac168da84d2e8"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p"
LANG      = "pt-BR"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

# Cache com TTL de 1 hora — evita re-buscar a cada restart
_cache      = {}
_cache_lock = threading.Lock()
_cache_time = {}
CACHE_TTL   = 3600


def tmdb_get(endpoint, extra_params=""):
    key = endpoint + extra_params
    now = time.time()
    with _cache_lock:
        if key in _cache and (now - _cache_time.get(key, 0)) < CACHE_TTL:
            return _cache[key]

    sep = "&" if "?" in endpoint else "?"
    url = f"{TMDB_BASE}{endpoint}{sep}api_key={TMDB_KEY}&language={LANG}{extra_params}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent":      "VoidFlix/1.0",
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as r:
            data = r.read()
            if r.info().get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            result = json.loads(data.decode("utf-8"))
            with _cache_lock:
                _cache[key]      = result
                _cache_time[key] = time.time()
            return result
    except Exception as e:
        print(f"  [TMDB] Erro em {endpoint}: {e}")
        return {}


def fetch_raw(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "VoidFlix/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "application/octet-stream")
        return data, ctype


ENDPOINTS = {
    "movies_trending":   ("/trending/movie/week",   ""),
    "movies_popular":    ("/movie/popular",          ""),
    "movies_toprated":   ("/movie/top_rated",        ""),
    "movies_nowplaying": ("/movie/now_playing",      ""),
    "movies_upcoming":   ("/movie/upcoming",         ""),
    "movies_action":     ("/discover/movie",         "&with_genres=28&sort_by=popularity.desc"),
    "movies_comedy":     ("/discover/movie",         "&with_genres=35&sort_by=popularity.desc"),
    "movies_horror":     ("/discover/movie",         "&with_genres=27&sort_by=popularity.desc"),
    "movies_scifi":      ("/discover/movie",         "&with_genres=878&sort_by=popularity.desc"),
    "movies_drama":      ("/discover/movie",         "&with_genres=18&sort_by=popularity.desc"),
    "tv_trending":       ("/trending/tv/week",       ""),
    "tv_popular":        ("/tv/popular",             ""),
    "tv_toprated":       ("/tv/top_rated",           ""),
    "tv_onair":          ("/tv/on_the_air",          ""),
    "tv_animation":      ("/discover/tv",            "&with_genres=16&sort_by=popularity.desc"),
    "tv_drama":          ("/discover/tv",            "&with_genres=18&sort_by=popularity.desc"),
    "tv_scifi":          ("/discover/tv",            "&with_genres=10765&sort_by=popularity.desc"),
    "tv_crime":          ("/discover/tv",            "&with_genres=80&sort_by=popularity.desc"),
    "kids_movies":       ("/discover/movie",         "&with_genres=16&certification_country=US&sort_by=popularity.desc"),
    "kids_tv":           ("/discover/tv",            "&with_genres=10762&sort_by=popularity.desc"),
    "sports_docs":       ("/discover/movie",         "&with_genres=99&with_keywords=6075&sort_by=popularity.desc"),
    "sports_tv":         ("/discover/tv",            "&with_genres=10764&sort_by=popularity.desc"),
}


class VoidFlixHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args): pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(200); self.cors(); self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._file(FRONTEND_FILE, "text/html; charset=utf-8")

        elif path == "/api/section":
            sid = params.get("id", [""])[0]
            if sid not in ENDPOINTS:
                self._json({"error": "unknown section"}); return
            ep, extra = ENDPOINTS[sid]
            data  = tmdb_get(ep, extra)
            items = data.get("results", [])[:15]   # 15 itens — menos DOM
            self._json({"items": items, "section": sid})

        elif path == "/api/detail":
            tid  = params.get("id",   [""])[0]
            kind = params.get("kind", ["movie"])[0]
            # Busca detalhes, vídeos e elenco em paralelo
            results = {}
            def fetch(key, ep, extra=""):
                results[key] = tmdb_get(ep, extra)
            threads = [
                threading.Thread(target=fetch, args=("detail",  f"/{kind}/{tid}")),
                threading.Thread(target=fetch, args=("videos",  f"/{kind}/{tid}/videos")),
                threading.Thread(target=fetch, args=("credits", f"/{kind}/{tid}/credits")),
            ]
            for t in threads: t.start()
            for t in threads: t.join()
            trailer = next(
                (v for v in results["videos"].get("results", [])
                 if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
                None
            )
            cast = results["credits"].get("cast", [])[:5]
            self._json({"detail": results["detail"], "trailer": trailer, "cast": cast})

        elif path == "/api/search":
            q    = params.get("q",    [""])[0]
            page = params.get("page", ["1"])[0]
            if not q:
                self._json({"results": []}); return
            data    = tmdb_get("/search/multi", f"&query={urllib.parse.quote(q)}&page={page}&include_adult=false")
            results = [r for r in data.get("results", []) if r.get("media_type") in ("movie","tv")]
            self._json({"results": results, "total": data.get("total_results", 0)})

        elif path == "/api/image":
            size    = params.get("size", ["w500"])[0]
            imgpath = params.get("path", [""])[0]
            if not imgpath:
                self.send_response(404); self.end_headers(); return
            img_url = f"{TMDB_IMG}/{size}{imgpath}"
            try:
                data, ctype = fetch_raw(img_url)
                self.send_response(200)
                self.send_header("Content-Type",   ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control",  "public, max-age=604800")  # 7 dias
                self.cors()
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_response(404); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    def _file(self, fp, ctype):
        try:
            with open(fp, "rb") as f: content = f.read()
            self.send_response(200)
            self.send_header("Content-Type",   ctype)
            self.send_header("Content-Length", str(len(content)))
            self.cors(); self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()
            self.wfile.write(b"index.html not found")

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.cors(); self.end_headers()
        self.wfile.write(data)


def preload():
    priority = ["movies_trending","tv_trending","movies_nowplaying","tv_onair","kids_tv","tv_animation"]
    print("\n[VoidFlix] Pré-carregando catálogo TMDB...")
    for sid in priority:
        ep, extra = ENDPOINTS[sid]
        tmdb_get(ep, extra)
        time.sleep(0.1)
    print("[VoidFlix] Catálogo pronto!\n")


def main():
    print("=" * 52)
    print("  VOIDFLIX — Servidor  |  TMDB Edition")
    print(f"  http://0.0.0.0:{PORT}")
    print("=" * 52)

    if not os.path.exists(FRONTEND_FILE):
        print(f"\n[ERRO] index.html não encontrado em: {FRONTEND_FILE}")
        input("Pressione Enter para sair...")
        sys.exit(1)

    threading.Thread(target=preload, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), VoidFlixHandler)
    print(f"\n[VoidFlix] Rodando em http://0.0.0.0:{PORT}")
    print("[VoidFlix] Ctrl+C para encerrar\n")

    # Abre navegador apenas se estiver rodando localmente
    if os.environ.get("RENDER") is None:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[VoidFlix] Encerrando..."); server.shutdown()


if __name__ == "__main__":
    main()
