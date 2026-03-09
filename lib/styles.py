"""
Shared premium styling for Zeitgeist: The Sports Interest Index.

Every page should call ``apply_premium_theme()`` immediately after
``st.set_page_config()``.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------

LEAGUE_COLORS = {
    "NBA": "#1D428A",
    "MLB": "#BF0D3E",
    "NHL": "#000000",
}

COLORS = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F8F9FA",
    "bg_card": "#FFFFFF",
    "border": "#E8EAED",
    "border_light": "#F0F1F3",
    "text_primary": "#1A1A2E",
    "text_secondary": "#6B7280",
    "text_muted": "#9CA3AF",
    "accent": "#1D428A",
    "success": "#059669",
    "warning": "#D97706",
    "danger": "#DC2626",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def apply_premium_theme() -> None:
    """Inject global CSS for the Zeitgeist premium theme."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header with optional subtitle."""
    sub = f'<p class="zg-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="zg-section-header"><h2>{title}</h2>{sub}</div>',
        unsafe_allow_html=True,
    )


def metric_card(
    label: str,
    value: str,
    delta: str = "",
    accent_color: str = COLORS["accent"],
) -> str:
    """Return HTML for a single premium metric card."""
    delta_html = ""
    if delta:
        positive = not delta.startswith("-")
        arrow = "&#9650;" if positive else "&#9660;"
        color = COLORS["success"] if positive else COLORS["danger"]
        delta_html = (
            f'<div class="zg-metric-delta" style="color:{color}">'
            f"{arrow} {delta}</div>"
        )
    return (
        f'<div class="zg-metric-card" style="border-top:3px solid {accent_color}">'
        f'  <div class="zg-metric-label">{label}</div>'
        f'  <div class="zg-metric-value">{value}</div>'
        f"  {delta_html}"
        f"</div>"
    )


def nav_card(title: str, description: str, icon: str = "") -> str:
    """Return HTML for a navigation card on the home page."""
    return (
        f'<div class="zg-nav-card">'
        f'  <div class="zg-nav-card-icon">{icon}</div>'
        f'  <div class="zg-nav-card-title">{title}</div>'
        f'  <div class="zg-nav-card-desc">{description}</div>'
        f"</div>"
    )


def data_freshness_badge(label: str, status: str) -> str:
    """Return HTML for the data freshness status badge."""
    status_colors = {
        "Fresh": COLORS["success"],
        "Aging": COLORS["warning"],
        "Stale": COLORS["danger"],
    }
    color = status_colors.get(status, COLORS["text_muted"])
    return (
        f'<div class="zg-freshness">'
        f'  <span class="zg-freshness-dot" style="background:{color}"></span>'
        f'  <span class="zg-freshness-label">{label}</span>'
        f'  <span class="zg-freshness-status" style="color:{color}">{status}</span>'
        f"</div>"
    )


def card_container(content_html: str) -> None:
    """Wrap arbitrary HTML in a premium card container."""
    st.markdown(
        f'<div class="zg-card">{content_html}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

_GLOBAL_CSS = """
<style>
/* ===== Font ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid #E8EAED;
}

/* ===== Layout ===== */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: #F8F9FA;
    border-right: 1px solid #E8EAED;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2 {
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6B7280;
}

/* ===== Typography ===== */
h1 {
    font-weight: 700;
    font-size: 1.75rem;
    color: #1A1A2E;
    letter-spacing: -0.02em;
}
h2 {
    font-weight: 600;
    font-size: 1.25rem;
    color: #1A1A2E;
    letter-spacing: -0.01em;
    margin-top: 1.5rem;
}
h3 {
    font-weight: 600;
    font-size: 1.05rem;
    color: #374151;
}
p, li, span {
    line-height: 1.6;
}

/* ===== Section header ===== */
.zg-section-header {
    border-bottom: 2px solid #E8EAED;
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
    margin-top: 2rem;
}
.zg-section-header h2 {
    margin: 0;
    padding: 0;
}
.zg-subtitle {
    font-size: 0.875rem;
    color: #6B7280;
    margin-top: 0.25rem;
}

/* ===== Cards ===== */
.zg-card {
    background: #FFFFFF;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s ease;
}
.zg-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

/* ===== Metric cards ===== */
.zg-metric-card {
    background: #FFFFFF;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    text-align: center;
}
.zg-metric-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6B7280;
    margin-bottom: 0.5rem;
}
.zg-metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #1A1A2E;
    line-height: 1.2;
}
.zg-metric-delta {
    font-size: 0.8rem;
    font-weight: 500;
    margin-top: 0.25rem;
}

/* ===== Data freshness badge ===== */
.zg-freshness {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: #F8F9FA;
    border-radius: 8px;
    font-size: 0.8rem;
}
.zg-freshness-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
.zg-freshness-label {
    color: #6B7280;
}
.zg-freshness-status {
    font-weight: 600;
    margin-left: auto;
}

/* ===== Navigation cards ===== */
.zg-nav-card {
    background: #FFFFFF;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
    height: 100%;
}
.zg-nav-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    border-color: #D1D5DB;
    transform: translateY(-1px);
}
.zg-nav-card-icon {
    font-size: 1.5rem;
    margin-bottom: 0.75rem;
}
.zg-nav-card-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1A1A2E;
    margin-bottom: 0.375rem;
}
.zg-nav-card-desc {
    font-size: 0.8rem;
    color: #6B7280;
    line-height: 1.5;
}

/* ===== Hero section ===== */
.zg-hero {
    background: linear-gradient(135deg, #F8F9FA 0%, #EEF0F4 50%, #E8EAED 100%);
    border-radius: 16px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    text-align: center;
    border: 1px solid #E8EAED;
}
.zg-hero-title {
    font-size: 2.5rem;
    font-weight: 700;
    color: #1A1A2E;
    letter-spacing: -0.03em;
    margin: 0;
    line-height: 1.2;
}
.zg-hero-tagline {
    font-size: 1rem;
    color: #6B7280;
    margin-top: 0.75rem;
    font-weight: 400;
    letter-spacing: 0.01em;
}

/* ===== Streamlit metric override ===== */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="stMetric"] label {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6B7280 !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: #1A1A2E !important;
}

/* ===== Tables ===== */
[data-testid="stDataFrame"] {
    border: 1px solid #E8EAED;
    border-radius: 8px;
    overflow: hidden;
}

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 2px solid #E8EAED;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.85rem;
    font-weight: 500;
    color: #6B7280;
    padding: 0.75rem 1.25rem;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
}
.stTabs [aria-selected="true"] {
    font-weight: 600 !important;
    color: #1D428A !important;
    border-bottom-color: #1D428A !important;
}

/* ===== Expander ===== */
[data-testid="stExpander"] {
    border: 1px solid #E8EAED;
    border-radius: 8px;
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    font-weight: 500;
    font-size: 0.9rem;
}

/* ===== League accent utilities ===== */
.league-accent-nba { border-left: 3px solid #1D428A; padding-left: 0.75rem; }
.league-accent-mlb { border-left: 3px solid #BF0D3E; padding-left: 0.75rem; }
.league-accent-nhl { border-left: 3px solid #000000; padding-left: 0.75rem; }

/* ===== Badges ===== */
.zg-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.zg-badge-success { background: #ECFDF5; color: #059669; }
.zg-badge-warning { background: #FFFBEB; color: #D97706; }
.zg-badge-danger  { background: #FEF2F2; color: #DC2626; }
.zg-badge-info    { background: #EFF6FF; color: #1D428A; }

/* ===== Alert callout ===== */
.zg-alert {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    font-size: 0.875rem;
    color: #92400E;
    margin-bottom: 1rem;
}

/* ===== Source card grid ===== */
.zg-source-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-top: 0.5rem;
}
.zg-source-card {
    background: #F8F9FA;
    border: 1px solid #E8EAED;
    border-radius: 8px;
    padding: 0.75rem 1rem;
}
.zg-source-name {
    font-size: 0.8rem;
    font-weight: 600;
    color: #1A1A2E;
}
.zg-source-desc {
    font-size: 0.7rem;
    color: #6B7280;
    margin-top: 0.15rem;
}

/* ===== Divider ===== */
hr {
    border: none;
    border-top: 1px solid #E8EAED;
    margin: 1.5rem 0;
}
</style>
"""
