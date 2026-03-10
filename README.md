# Zeitgeist: The Sports Interest Index

**[View the live app](https://major-league-interest-map.streamlit.app)** | **[Read the blog post](https://narendranag.github.io/2026/03/10/zeitgeist-which-sports-teams-are-people-paying-attention-to.html)**

Zeitgeist tracks digital attention across all 92 NBA, MLB, and NHL teams using six independent data sources. It combines search interest, Wikipedia traffic, game results, Reddit engagement, news coverage, and streaming availability into a single configurable Interest Score — updated every six hours.

## Architecture

```
Pipeline (GitHub Actions, every 6h)        Streamlit App (read-only)
  Google Trends ──┐                        ┌── League Overview
  Wikipedia ──────┤                        ├── Team Deep Dive
  ESPN ───────────┼── parquet files ──────>├── Head to Head
  Reddit ─────────┤   (committed to git)   ├── Movers & Alerts
  Google News ────┘                        └── About
```

Data collection is fully decoupled from display. A scheduled GitHub Actions pipeline fetches all sources every six hours and commits parquet files to the `deploy` branch. The Streamlit app loads these into an in-memory DuckDB database on startup for instant queries.

## Data Sources

| Source | What it measures | Update frequency |
|--------|-----------------|------------------|
| **Google Trends** | Relative search interest (0-100) | Every 6h |
| **Wikipedia Pageviews** | Daily article views from Wikimedia API | Every 6h |
| **ESPN** | Game schedules, scores (W/L), broadcast channels | Every 6h |
| **Victory+** | Free streaming availability (detected from ESPN broadcasts) | Every 6h |
| **Reddit** | Community post volume and engagement (r/nba, r/baseball, r/hockey) | Every 6h |
| **Google News** | Daily article count per team | Every 6h |

### Victory+

[Victory+](https://victoryplus.com) is a free sports streaming platform. Zeitgeist detects Victory+ availability from ESPN broadcast data and highlights upcoming games that can be watched for free. Current Victory+ partners include the Anaheim Ducks, Dallas Stars, and Texas Rangers.

## Dashboard Pages

- **Home** — Hero section, data freshness indicator, quick stats, navigation
- **League Overview** — Rankings with configurable metric weights, bar chart, Top Movers (risers and fallers)
- **Team Deep Dive** — Single-team trendlines with W/L game annotations, upcoming schedule with Victory+ flags, Reddit buzz, news volume
- **Head to Head** — Compare 2-5 teams side by side across all metrics
- **Movers & Alerts** — Biggest risers/fallers and anomaly detection (statistical spikes)
- **About** — How the app works, data sources explained, Interest Score formula

## Running Locally

1. Clone the repository:

```bash
git clone https://github.com/narendranag/interest-map.git
cd interest-map
```

2. Install app dependencies:

```bash
pip install -r requirements.txt
```

3. Seed initial data (requires pipeline dependencies):

```bash
pip install -r requirements-pipeline.txt
python -m pipeline.run_pipeline
```

4. Run the app:

```bash
streamlit run Home.py
```

## Project Structure

```
Home.py                          # Home page (entrypoint)
pages/
  1_League_Overview.py
  2_Team_Deep_Dive.py
  3_Head_to_Head.py
  4_Movers_and_Alerts.py
  5_About.py
lib/                             # Shared modules
  teams.py                       # Team definitions, ESPN IDs, league metadata
  db.py                          # DuckDB in-memory loader
  scoring.py                     # Normalisation, weighted scoring, anomaly detection
  charts.py                      # Altair chart builders (Zeitgeist theme)
  styles.py                      # Global CSS injection and styling helpers
pipeline/                        # Data fetchers (run by GitHub Actions)
  fetch_trends.py                # Google Trends
  fetch_wikipedia.py             # Wikipedia pageviews
  fetch_espn.py                  # ESPN schedules, scores, broadcasts
  fetch_reddit.py                # Reddit community metrics (public JSON API)
  fetch_news.py                  # Google News RSS
  run_pipeline.py                # Orchestrator
data/                            # Pipeline output (parquet files)
.github/workflows/update_data.yml  # Scheduled pipeline (every 6h)
.streamlit/config.toml           # Theme configuration
```

## How the Interest Score Works

Each of five metrics (Trends, Wikipedia, ESPN win rate, Reddit, News) is normalised to a 0-100 scale using min-max scaling across all teams. The composite score is a weighted average:

**Interest Score = w₁ × Trends + w₂ × Wiki + w₃ × ESPN + w₄ × Reddit + w₅ × News**

Weights are configurable via sidebar sliders on the League Overview page and automatically re-normalise to sum to 1.0.

## Limitations

- Google Trends scores are relative (0-100 within the query), not absolute search volumes.
- Reddit uses the public JSON API with conservative rate limiting (~2s between requests).
- Wikipedia data typically lags by ~24 hours.
- Victory+ availability is inferred from ESPN broadcast data and a static list of known partner teams.
- ESPN API is unofficial and may change without notice.

## License

Open source. Built with Streamlit, DuckDB, and Altair.
