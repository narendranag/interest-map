# Team Interest Dashboard

**[View the live app](https://major-league-interest-map.streamlit.app)**

Compare daily digital attention across NBA, MLB, and NHL teams using six public proxy data sources. The dashboard ranks teams by a configurable weighted interest score, tracks trends over time, and flags statistical anomalies.

## Architecture

```
Pipeline (GitHub Actions, every 6h)        Streamlit App (read-only)
  Google Trends ──┐                        ┌── League Overview
  Wikipedia ──────┤                        ├── Team Deep Dive
  ESPN ───────────┼── parquet files ──────>├── Head to Head
  Reddit ─────────┤   (committed to git)   └── Movers & Alerts
  Google News ────┘
```

Data collection is fully decoupled from display. A scheduled GitHub Actions pipeline fetches all sources every six hours and commits parquet files to the `deploy` branch. The Streamlit app loads these into an in-memory DuckDB database on startup for instant queries.

## Data sources

| Source | What it measures | Update frequency |
|--------|-----------------|------------------|
| **Google Trends** | Relative search interest (0-100) | Every 6h |
| **Wikipedia Pageviews** | Daily article views from Wikimedia API | Every 6h |
| **ESPN** | Game schedules, scores (W/L), broadcast channels | Every 6h |
| **Victory+** | Free streaming availability (detected from ESPN broadcasts) | Every 6h |
| **Reddit** | Community post volume and engagement (r/nba, r/baseball, r/hockey) | Every 6h |
| **Google News** | Daily article count per team | Every 6h |

### Victory+

[Victory+](https://victoryplus.com) is a free sports streaming platform. The dashboard detects Victory+ availability from ESPN broadcast data and highlights upcoming games that can be watched for free. Current Victory+ partners include the Anaheim Ducks, Dallas Stars, and Texas Rangers.

## Dashboard pages

- **League Overview** — Rankings, bar chart, configurable metric weights, Top Movers (7-day delta)
- **Team Deep Dive** — Single-team trendlines with W/L game annotations, upcoming schedule with Victory+ flags, Reddit buzz, news volume
- **Head to Head** — Compare 2-5 teams side by side across all metrics
- **Movers & Alerts** — Biggest risers/fallers and anomaly detection (statistical spikes)

## Running locally

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

## Project structure

```
Home.py                          # Home page
pages/                          # Multi-page Streamlit dashboard
  1_League_Overview.py
  2_Team_Deep_Dive.py
  3_Head_to_Head.py
  4_Movers_and_Alerts.py
lib/                            # Shared modules
  teams.py                      # Team definitions, ESPN IDs, league metadata
  db.py                         # DuckDB in-memory loader
  scoring.py                    # Normalisation, weighted scoring, anomaly detection
  charts.py                     # Altair chart builders
pipeline/                       # Data fetchers (run by GitHub Actions)
  fetch_trends.py               # Google Trends
  fetch_wikipedia.py            # Wikipedia pageviews
  fetch_espn.py                 # ESPN schedules, scores, broadcasts
  fetch_reddit.py               # Reddit community metrics
  fetch_news.py                 # Google News RSS
  run_pipeline.py               # Orchestrator
data/                           # Pipeline output (parquet files)
.github/workflows/update_data.yml  # Scheduled pipeline
```

## Limitations

- Google Trends scores are relative (0-100 within the query), not absolute search volumes.
- Reddit unauthenticated API is limited to ~10 requests/minute; the pipeline takes ~10 minutes for all teams.
- Wikipedia data typically lags by ~24 hours.
- Victory+ availability is inferred from ESPN broadcast data and a static list of known partner teams.
- ESPN API is unofficial and may change without notice.
