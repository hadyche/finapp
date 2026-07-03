"""Reusable UI components."""
import streamlit as st


def open_stock_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.switch_page("pages/3_Stock_Detail.py")
