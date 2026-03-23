"""
Fix: httpx trust_env=True reads macOS system proxy (127.0.0.1:1082),
which breaks localhost requests to Ollama even though localhost is in
the proxy exception list — httpx's NO_PROXY handling has a bug.

Setting NO_PROXY env var ensures httpx skips proxy for localhost.
"""
import os
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
