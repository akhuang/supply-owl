"""
Patch httpx to work with Ollama.
Import this before importing openai or hermes.
httpx's default transport has compatibility issues with Ollama's server.
Forcing HTTPTransport() explicitly fixes it.
"""
import httpx

_orig_client_init = httpx.Client.__init__

def _patched_init(self, *args, **kwargs):
    if 'transport' not in kwargs:
        kwargs['transport'] = httpx.HTTPTransport()
    _orig_client_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_init
