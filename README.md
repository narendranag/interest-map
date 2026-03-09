# Team Interest Dashboard

This project is a lightweight web application that compares the daily interest in professional sports teams across the NBA, MLB, and NHL. While the long-term goal is to visualise bid-stream metrics (e.g. daily bid volume and bid rate per team) from an advertising platform, this dashboard uses public proxy datasets to approximate advertiser interest. The proxies let you prototype the pipeline and explore surging teams before integrating proprietary data.

## Data sources

### Google Trends (relative search interest)

We pull historical interest for each team name from Google Trends. Google Trends reports search interest as a relative score (0–100) scaled to the peak value in the selected time period; values are not absolute search volumes. A downward trend means the team's relative popularity is falling compared with all other Google searches, not necessarily that absolute search volume is declining. Google Trends also excludes low-volume queries and removes duplicate searches from the same user.

We use the pytrends client (unofficial Google Trends API). Pytrends restricts time-window options: daily data is available only for 1- or 7-day windows (e.g., `now 1-d`, `now 7-d`), and monthly data for 1, 3, or 12 months (e.g., `today 1-m`, `today 3-m`, `today 12-m`). The app maps the user-selected window to one of these valid timeframes when requesting data.

### Wikipedia Pageviews (news-driven attention)

As a second proxy for advertiser interest, the app queries the Wikimedia REST API for daily pageview counts of each team's Wikipedia article. The `/metrics/pageviews/per-article/<project>/<access>/<agent>/<article>/daily/<start>/<end>` endpoint returns views per day for a given article and date range. Wikipedia pageviews capture spikes in attention driven by news events (trades, injuries, playoff runs) and complement search interest.

### YouTube channel statistics (optional)

If you supply a YouTube Data API v3 key in the sidebar, the app fetches total view and subscriber counts for each team's official YouTube channel. These counts are point-in-time totals (not daily series) and are useful for ranking overall digital presence. Without an API key this source is skipped and its weight is redistributed across the other two metrics.

## Approach

1. Compile team lists: the app contains complete lists of NBA, MLB and NHL teams. Each team name is used as a query term for the data sources.
2. Fetch Google Trends: using pytrends, the app fetches interest over time for each team in batches of 5. The selected window of n days is mapped to a valid timeframe (`now 7-d`, `today 1-m`, `today 3-m`, `today 12-m`) to satisfy API requirements.
3. Fetch Wikipedia pageviews: for each team, the app calls the Wikimedia API to retrieve daily pageview counts between the selected start and end dates.
4. Fetch YouTube stats (optional): if an API key is provided, total views and subscribers are pulled for each team's channel.
5. Normalise and blend metrics: each metric is normalised per team to the 0–100 range and an interest score is computed as a weighted blend. Weights are configurable through sidebar sliders and are automatically normalised to sum to 1.
6. Interactive dashboard: built with Streamlit, the dashboard lets you filter by league, choose a time window, rank by any metric, and adjust weights. It shows a ranking table, bar chart, trend lines, a "top movers" table, and an expandable metric breakdown.
7. Ready for real bid data: replace the `fetch_interest_proxies` function with a warehouse query returning `date`, `league`, `team`, `bid_volume`, and `bid_rate` to visualise your own metrics.

## Limitations and considerations

- Google Trends is relative: scores are normalised and not directly comparable across queries.
- Coverage: low-search-volume teams may return zeros.
- Delay: Wikipedia data typically lags by ~24 hours.
- Noise: these proxies measure general attention rather than actual ad bids.
- YouTube quota: the YouTube Data API has a daily quota of 10,000 units. A full fetch for all teams uses most of this quota on the first load (results are cached for one hour).

## Running locally

1. Clone or download this repository.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run the app and open it in your browser:

```bash
streamlit run app.py
# then open http://localhost:8501
```
