import requests
import json
from chalice import Chalice, Cron
from chalicelib.creds import fantasy_api_endpoint, discord_webhook_url

app = Chalice(app_name='fantasy-lambda')
app.debug = True

TRENDING_ENDPOINT = fantasy_api_endpoint
WEBHOOK_URL = discord_webhook_url


# Load in player_name -> player_id map into memory from file
def get_player_data():
    with open("./chalicelib/player-map.json") as f:
        data = json.load(f)
    return data


# Request trending adds, return parsed dictionary
def get_trending_adds(player_data):
    players_raw = requests.get(f"{TRENDING_ENDPOINT}/add").json()[:10]
    return parse_trending_players(players_raw, player_data)


# Request trending drops, return parsed dictionary
def get_trending_drops(player_data):
    players_raw = requests.get(f"{TRENDING_ENDPOINT}/drop").json()[:10]
    return parse_trending_players(players_raw, player_data)


# Parse out important attributes from response and return dictionary
def parse_trending_players(players_raw, player_data):
    players = []
    for player in players_raw:
        players.append(
            {
                "name": f"{player_data.get(player['player_id'])['first_name']} {player_data.get(player['player_id'])['last_name']}",
                "position": ','.join(player_data.get(player['player_id'])['fantasy_positions']),
                "trend": player.get('count')
            }
        )
    return players


# Formate the data in a Discord friendly manner then POST to webhook URL
def bundle_and_send(players, trend):
    trending_players = '\n'.join([f"- **Name**: {player['name']}\n  Positions: {player['position']}\n  Trend: {player['trend']} {trend}s in last 24 Hours\n" for player in players])
    discord_payload = f"\n**__TRENDING {trend.upper()}:__**\n{trending_players}\n------------------------------"
    r = requests.post(
        url = WEBHOOK_URL,
        data = {'content': discord_payload, 'wait':'true'}
    )    
    print(r.json())
    try:
        r.raise_for_status()    
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {r.status_code} - {r.json()}")
        exit(1)


@app.route('/')
def homepage():
    return {'Fantasy Rest API': ['/adds', '/drops']}


# Display trending adds on API endpoint
@app.route('/adds')
def adds_endpoint():
    player_data = get_player_data()
    trending_adds = get_trending_adds(player_data)
    return {"adds": trending_adds}


# Display trending drops on API endpoint
@app.route('/drops')
def adds_endpoint():
    player_data = get_player_data()
    trending_drops = get_trending_drops(player_data)
    return {"drops": trending_drops}


# Post results to discord channel daily 
# local dev - @app.route('/')
@app.schedule(Cron('0', '13', '*', '*', '?', '*')) #- Everyday 9am EST
def discord_lambda(event):
    player_data = get_player_data()

    trending_adds = get_trending_adds(player_data)
    bundle_and_send(trending_adds, "adds")

    trending_drops = get_trending_drops(player_data)
    bundle_and_send(trending_drops, "drops")
