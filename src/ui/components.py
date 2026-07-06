"""Reusable UI components."""
import streamlit as st


def open_stock_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    try:
        st.query_params["t"] = ticker
    except Exception:
        pass
    st.switch_page("pages/3_Stock_Detail.py")


def info_popover(label: str, md: str):
    """A little ⓘ button that explains something in plain words."""
    with st.popover(f"ⓘ {label}"):
        st.markdown(md)


GLOSSARY = """
**Stock** — a tiny piece of a company you can buy. If the company does well, your piece is worth more.

**Ticker** — a stock's nickname, like **AAPL** for Apple. Every stock has one.

**Company value (market cap)** — what the *whole* company is worth if you added up every share.

**Government deal (federal contract)** — the U.S. government paying a company to do work. This is public information — anyone can see it.

**Insider** — a boss at a company (like the CEO). When bosses buy their *own* company's stock with their *own* money, they think it's going up.

**S&P 500** — the 500 biggest U.S. companies. Think of it as the "average" of the stock market.

**Hard to trade (thin volume)** — very few people buy or sell this stock each day, so trading it can be tricky.
"""


def glossary_popover():
    """Shared dictionary of terms, in plain words."""
    with st.popover("📖 What do these words mean?"):
        st.markdown(GLOSSARY)
