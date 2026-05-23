"""Favorites management — session-scoped (resets on refresh)."""
import streamlit as st


def _init():
    if "favorites" not in st.session_state:
        st.session_state.favorites = set()


def get_favorites() -> set[str]:
    _init()
    return st.session_state.favorites


def add_favorite(ticker: str) -> None:
    _init()
    st.session_state.favorites.add(ticker.upper())


def remove_favorite(ticker: str) -> None:
    _init()
    st.session_state.favorites.discard(ticker.upper())


def toggle_favorite(ticker: str) -> bool:
    _init()
    t = ticker.upper()
    if t in st.session_state.favorites:
        st.session_state.favorites.discard(t)
        return False
    st.session_state.favorites.add(t)
    return True


def is_favorite(ticker: str) -> bool:
    _init()
    return ticker.upper() in st.session_state.favorites
