"""
Saved stocks that travel in the web address.

Streamlit Cloud has no server-side accounts, so the watchlist lives in
the ?w= query parameter: hydrated once per session from the URL, and
written back on every change. Bookmarking the page = saving your list.
"""
import re

try:
    import streamlit as st
except ImportError:  # pure helpers stay importable in test environments
    st = None

_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")


def parse_watchlist_param(raw: str) -> set[str]:
    """'mrcy,tls,junk!!' → {'MRCY', 'TLS'}. Pure — unit-testable."""
    out = set()
    for part in str(raw or "").split(","):
        t = part.strip().upper()
        if t and _TICKER_RE.match(t):
            out.add(t)
    return out


def _sync():
    """Mirror the current set into the URL so bookmarks capture it."""
    try:
        favs = st.session_state.favorites
        if favs:
            st.query_params["w"] = ",".join(sorted(favs))
        elif "w" in st.query_params:
            del st.query_params["w"]
    except Exception:
        pass  # query params unavailable in bare test contexts


def _init():
    if "favorites" not in st.session_state:
        st.session_state.favorites = set()
    if not st.session_state.get("_favs_hydrated"):
        st.session_state["_favs_hydrated"] = True
        try:
            from_url = parse_watchlist_param(st.query_params.get("w", ""))
            if from_url:
                st.session_state.favorites |= from_url
        except Exception:
            pass


def get_favorites() -> set[str]:
    _init()
    return st.session_state.favorites


def add_favorite(ticker: str) -> None:
    _init()
    st.session_state.favorites.add(ticker.upper())
    _sync()


def remove_favorite(ticker: str) -> None:
    _init()
    st.session_state.favorites.discard(ticker.upper())
    _sync()


def toggle_favorite(ticker: str) -> bool:
    _init()
    t = ticker.upper()
    if t in st.session_state.favorites:
        st.session_state.favorites.discard(t)
        _sync()
        return False
    st.session_state.favorites.add(t)
    _sync()
    return True


def is_favorite(ticker: str) -> bool:
    _init()
    return ticker.upper() in st.session_state.favorites
