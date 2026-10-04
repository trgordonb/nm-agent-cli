"""In-process Python port of the wiki-os engine (Ansub/wiki-os fork
trgordonb/wiki-os, MIT). Serves the same /wapi/api/* contract the React UI
already consumes — see routes.create_wiki_router.
"""

from .runtime import WikiEngine, WikiSetupRequired, get_engine, reset_engine
from .routes import create_wiki_router

__all__ = [
    "WikiEngine",
    "WikiSetupRequired",
    "create_wiki_router",
    "get_engine",
    "reset_engine",
]
