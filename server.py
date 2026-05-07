"""
VOIDFLIX - Servidor Local com TMDB API
Roda em http://localhost:8765
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

PORT = 8765
FRONTEND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# ── TMDB ──────────────────────────────────────────────────────────────
# Chave pública gratuita (read-only, segura para usar)
TMDB_KEY  = "8265bd1679663a7ea12ac168da84d2e8"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p"
LANG      = "pt-BR"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

_cache      = {}
_cache_lock = threading.Lock()


def tmdb_get(endpoint, extra_params=""):
    key = endpoint + extra_params
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    sep = "&" if "?" in endpoint else "?"
    url = f"{TMDB_BASE}{endpoint}{sep}api_key={TMDB_KEY}&language={LANG}{extra_params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VoidFlix/1.0"})
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as r:
            data = r.read()
            if r.info().get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            result = json.loads(data.decode("utf-8"))
            with _cache_lock:
                _cache[key] = result
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


# ─────────────────────────────────────────────────────────────────────
# ENDPOINTS TMDB que o frontend vai usar
# ─────────────────────────────────────────────────────────────────────
ENDPOINTS = {
    # Filmes
    "movies_trending":   ("/trending/movie/week",          ""),
    "movies_popular":    ("/movie/popular",                 ""),
    "movies_toprated":   ("/movie/top_rated",               ""),
    "movies_nowplaying": ("/movie/now_playing",             ""),
    "movies_upcoming":   ("/movie/upcoming",                ""),
    "movies_action":     ("/discover/movie",                "&with_genres=28&sort_by=popularity.desc"),
    "movies_comedy":     ("/discover/movie",                "&with_genres=35&sort_by=popularity.desc"),
    "movies_horror":     ("/discover/movie",                "&with_genres=27&sort_by=popularity.desc"),
    "movies_scifi":      ("/discover/movie",                "&with_genres=878&sort_by=popularity.desc"),
    "movies_drama":      ("/discover/movie",                "&with_genres=18&sort_by=popularity.desc"),
    # Séries
    "tv_trending":       ("/trending/tv/week",              ""),
    "tv_popular":        ("/tv/popular",                    ""),
    "tv_toprated":       ("/tv/top_rated",                  ""),
    "tv_onair":          ("/tv/on_the_air",                 ""),
    "tv_animation":      ("/discover/tv",                   "&with_genres=16&sort_by=popularity.desc"),
    "tv_drama":          ("/discover/tv",                   "&with_genres=18&sort_by=popularity.desc"),
    "tv_scifi":          ("/discover/tv",                   "&with_genres=10765&sort_by=popularity.desc"),
    "tv_crime":          ("/discover/tv",                   "&with_genres=80&sort_by=popularity.desc"),
    # Kids
    "kids_movies":       ("/discover/movie",                "&with_genres=16&certification_country=US&sort_by=popularity.desc"),
    "kids_tv":           ("/discover/tv",                   "&with_genres=10762&sort_by=popularity.desc"),
    # Esportes (documentários esportivos)
    "sports_docs":       ("/discover/movie",                "&with_genres=99&with_keywords=6075&sort_by=popularity.desc"),
    "sports_tv":         ("/discover/tv",                   "&with_genres=10764&sort_by=popularity.desc"),
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

        # ── Frontend ──────────────────────────────────────────────────
        if path in ("/", "/index.html"):
            self._file(FRONTEND_FILE, "text/html; charset=utf-8")

        # ── Seção de catálogo ─────────────────────────────────────────
        elif path == "/api/section":
            sid = params.get("id", [""])[0]
            if sid not in ENDPOINTS:
                self._json({"error": "unknown section"}); return
            ep, extra = ENDPOINTS[sid]
            data = tmdb_get(ep, extra)
            items = data.get("results", [])[:20]
            self._json({"items": items, "section": sid})

        # ── Detalhes de item ──────────────────────────────────────────
        elif path == "/api/detail":
            tid  = params.get("id",   [""])[0]
            kind = params.get("kind", ["movie"])[0]   # movie | tv
            ep_detail = f"/{kind}/{tid}"
            ep_videos = f"/{kind}/{tid}/videos"
            ep_credits= f"/{kind}/{tid}/credits"
            detail  = tmdb_get(ep_detail)
            videos  = tmdb_get(ep_videos)
            credits = tmdb_get(ep_credits)
            # Pega o primeiro trailer do YouTube
            trailer = next(
                (v for v in videos.get("results", [])
                 if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
                None
            )
            # Top 5 do elenco
            cast = credits.get("cast", [])[:5]
            self._json({
                "detail":  detail,
                "trailer": trailer,
                "cast":    cast,
            })

        # ── Busca ─────────────────────────────────────────────────────
        elif path == "/api/search":
            q    = params.get("q",    [""])[0]
            page = params.get("page", ["1"])[0]
            if not q:
                self._json({"results": []}); return
            data = tmdb_get("/search/multi", f"&query={urllib.parse.quote(q)}&page={page}&include_adult=false")
            # filtra só filmes e séries (remove pessoas etc.)
            results = [r for r in data.get("results", []) if r.get("media_type") in ("movie","tv")]
            self._json({"results": results, "total": data.get("total_results", 0)})

        # ── Proxy de imagens TMDB (evita mixed-content) ───────────────
        elif path == "/api/image":
            size   = params.get("size", ["w500"])[0]
            imgpath= params.get("path", [""])[0]
            if not imgpath:
                self.send_response(404); self.end_headers(); return
            img_url = f"{TMDB_IMG}/{size}{imgpath}"
            try:
                data, ctype = fetch_raw(img_url)
                self.send_response(200)
                self.send_header("Content-Type",   ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control",  "public, max-age=86400")
                self.cors()
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_response(404); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────
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
            self.wfile.write(b"index.html not found - coloque server.py e index.html na mesma pasta")

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.cors(); self.end_headers()
        self.wfile.write(data)


def preload():
    """Pré-carrega as seções mais importantes em background."""
    priority = ["movies_trending","tv_trending","movies_nowplaying","tv_onair","kids_tv","tv_animation"]
    print("\n[VoidFlix] Pré-carregando catálogo TMDB...")
    for sid in priority:
        ep, extra = ENDPOINTS[sid]
        tmdb_get(ep, extra)
        time.sleep(0.15)
    print("[VoidFlix] Catálogo pronto!\n")


def main():
    print("=" * 52)
    print("  VOIDFLIX — Servidor Local  |  TMDB Edition")
    print(f"  http://localhost:{PORT}")
    print("=" * 52)

    if not os.path.exists(FRONTEND_FILE):
        print(f"\n[ERRO] index.html não encontrado em: {FRONTEND_FILE}")
        print("Certifique-se de que server.py e index.html estão na mesma pasta.\n")
        input("Pressione Enter para sair...")
        sys.exit(1)

    threading.Thread(target=preload, daemon=True).start()

    server = http.server.ThreadingHTTPServer(("localhost", PORT), VoidFlixHandler)
    print(f"\n[VoidFlix] Rodando em http://localhost:{PORT}")
    print("[VoidFlix] Abrindo navegador...")
    print("[VoidFlix] Ctrl+C ou feche esta janela para encerrar\n")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[VoidFlix] Encerrando..."); server.shutdown()


if __name__ == "__main__":
    main()
