"""
Shared team definitions, ESPN identifiers, and league metadata.

Every module in the project imports team lists and lookup tables from here
so there is a single source of truth.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Team rosters
# ---------------------------------------------------------------------------

NBA_TEAMS: List[str] = [
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
    "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks",
    "Denver Nuggets", "Detroit Pistons", "Golden State Warriors",
    "Houston Rockets", "Indiana Pacers", "LA Clippers",
    "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
    "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
    "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
    "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
    "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
    "Utah Jazz", "Washington Wizards",
]

MLB_TEAMS: List[str] = [
    "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles",
    "Boston Red Sox", "Chicago Cubs", "Chicago White Sox",
    "Cincinnati Reds", "Cleveland Guardians", "Colorado Rockies",
    "Detroit Tigers", "Houston Astros", "Kansas City Royals",
    "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins",
    "Milwaukee Brewers", "Minnesota Twins", "New York Mets",
    "New York Yankees", "Oakland Athletics", "Philadelphia Phillies",
    "Pittsburgh Pirates", "San Diego Padres", "San Francisco Giants",
    "Seattle Mariners", "St. Louis Cardinals", "Tampa Bay Rays",
    "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
]

NHL_TEAMS: List[str] = [
    "Anaheim Ducks", "Boston Bruins", "Buffalo Sabres",
    "Calgary Flames", "Carolina Hurricanes", "Chicago Blackhawks",
    "Colorado Avalanche", "Columbus Blue Jackets", "Dallas Stars",
    "Detroit Red Wings", "Edmonton Oilers", "Florida Panthers",
    "Los Angeles Kings", "Minnesota Wild", "Montreal Canadiens",
    "Nashville Predators", "New Jersey Devils", "New York Islanders",
    "New York Rangers", "Ottawa Senators", "Philadelphia Flyers",
    "Pittsburgh Penguins", "San Jose Sharks", "Seattle Kraken",
    "St. Louis Blues", "Tampa Bay Lightning", "Toronto Maple Leafs",
    "Utah Hockey Club", "Vancouver Canucks", "Vegas Golden Knights",
    "Washington Capitals", "Winnipeg Jets",
]

LEAGUE_TEAMS: Dict[str, List[str]] = {
    "NBA": NBA_TEAMS,
    "MLB": MLB_TEAMS,
    "NHL": NHL_TEAMS,
}

TEAM_TO_LEAGUE: Dict[str, str] = {
    team: league for league, teams in LEAGUE_TEAMS.items() for team in teams
}

ALL_TEAMS: List[str] = [t for teams in LEAGUE_TEAMS.values() for t in teams]

# ---------------------------------------------------------------------------
# ESPN integration
# ---------------------------------------------------------------------------

ESPN_SPORT_PATHS: Dict[str, str] = {
    "NBA": "basketball/nba",
    "MLB": "baseball/mlb",
    "NHL": "hockey/nhl",
}

# Mapping: our canonical team name -> ESPN numeric team ID.
# Sourced from https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams
ESPN_TEAM_IDS: Dict[str, int] = {
    # NBA
    "Atlanta Hawks": 1, "Boston Celtics": 2, "Brooklyn Nets": 17,
    "Charlotte Hornets": 30, "Chicago Bulls": 4, "Cleveland Cavaliers": 5,
    "Dallas Mavericks": 6, "Denver Nuggets": 7, "Detroit Pistons": 8,
    "Golden State Warriors": 9, "Houston Rockets": 10, "Indiana Pacers": 11,
    "LA Clippers": 12, "Los Angeles Lakers": 13, "Memphis Grizzlies": 29,
    "Miami Heat": 14, "Milwaukee Bucks": 15, "Minnesota Timberwolves": 16,
    "New Orleans Pelicans": 3, "New York Knicks": 18, "Oklahoma City Thunder": 25,
    "Orlando Magic": 19, "Philadelphia 76ers": 20, "Phoenix Suns": 21,
    "Portland Trail Blazers": 22, "Sacramento Kings": 23, "San Antonio Spurs": 24,
    "Toronto Raptors": 28, "Utah Jazz": 26, "Washington Wizards": 27,
    # MLB
    "Arizona Diamondbacks": 29, "Atlanta Braves": 15, "Baltimore Orioles": 1,
    "Boston Red Sox": 2, "Chicago Cubs": 16, "Chicago White Sox": 4,
    "Cincinnati Reds": 17, "Cleveland Guardians": 5, "Colorado Rockies": 27,
    "Detroit Tigers": 6, "Houston Astros": 18, "Kansas City Royals": 7,
    "Los Angeles Angels": 3, "Los Angeles Dodgers": 19, "Miami Marlins": 28,
    "Milwaukee Brewers": 8, "Minnesota Twins": 9, "New York Mets": 21,
    "New York Yankees": 10, "Oakland Athletics": 11, "Philadelphia Phillies": 22,
    "Pittsburgh Pirates": 23, "San Diego Padres": 25, "San Francisco Giants": 26,
    "Seattle Mariners": 12, "St. Louis Cardinals": 24, "Tampa Bay Rays": 30,
    "Texas Rangers": 13, "Toronto Blue Jays": 14, "Washington Nationals": 20,
    # NHL
    "Anaheim Ducks": 25, "Boston Bruins": 1, "Buffalo Sabres": 2,
    "Calgary Flames": 3, "Carolina Hurricanes": 7, "Chicago Blackhawks": 4,
    "Colorado Avalanche": 17, "Columbus Blue Jackets": 29, "Dallas Stars": 9,
    "Detroit Red Wings": 5, "Edmonton Oilers": 6, "Florida Panthers": 26,
    "Los Angeles Kings": 8, "Minnesota Wild": 30, "Montreal Canadiens": 10,
    "Nashville Predators": 27, "New Jersey Devils": 11, "New York Islanders": 12,
    "New York Rangers": 13, "Ottawa Senators": 14, "Philadelphia Flyers": 15,
    "Pittsburgh Penguins": 16, "San Jose Sharks": 18, "Seattle Kraken": 124292,
    "St. Louis Blues": 19, "Tampa Bay Lightning": 20, "Toronto Maple Leafs": 21,
    "Utah Hockey Club": 129764, "Vancouver Canucks": 22,
    "Vegas Golden Knights": 37, "Washington Capitals": 23, "Winnipeg Jets": 28,
}

# ESPN sometimes returns different display names than our canonical names.
# This reverse-lookup maps ESPN displayName -> our canonical name.
ESPN_NAME_TO_CANONICAL: Dict[str, str] = {
    "Athletics": "Oakland Athletics",
    "Utah Mammoth": "Utah Hockey Club",
}
# Add identity mappings for all canonical names
for _name in ALL_TEAMS:
    ESPN_NAME_TO_CANONICAL.setdefault(_name, _name)

# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

REDDIT_SUBREDDITS: Dict[str, str] = {
    "NBA": "nba",
    "MLB": "baseball",
    "NHL": "hockey",
}

# ---------------------------------------------------------------------------
# Victory+ streaming
# ---------------------------------------------------------------------------

VICTORY_PLUS_TEAMS: Set[str] = {
    "Anaheim Ducks",
    "Dallas Stars",
    "Texas Rangers",
}

VICTORY_PLUS_BROADCAST_PATTERNS: List[str] = [
    "Victory+", "V+", "VictoryPlus", "victory+", "VICTORY+",
]

# ---------------------------------------------------------------------------
# Seasons (used for seasonal normalisation)
# ---------------------------------------------------------------------------

# (start_month, end_month) — for leagues that wrap around the year-end
# (e.g. NBA Oct-Apr) start_month > end_month.
SEASON_RANGES: Dict[str, Tuple[int, int]] = {
    "MLB": (4, 10),   # April – October
    "NBA": (10, 4),   # October – April
    "NHL": (10, 6),   # October – June
}
