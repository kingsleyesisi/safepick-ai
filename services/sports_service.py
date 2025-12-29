
import requests
from datetime import datetime, timedelta

class SportsService:
    # Configuration for supported leagues and their ESPN paths
    LEAGUES_CONFIG = {
        'epl': {'sport': 'soccer', 'slug': 'eng.1', 'name': 'Premier League'},
        'laliga': {'sport': 'soccer', 'slug': 'esp.1', 'name': 'La Liga'},
        'bundesliga': {'sport': 'soccer', 'slug': 'ger.1', 'name': 'Bundesliga'},
        'seriea': {'sport': 'soccer', 'slug': 'ita.1', 'name': 'Serie A'},
        'ucl': {'sport': 'soccer', 'slug': 'uefa.champions', 'name': 'Champions League'},
        'ligue1': {'sport': 'soccer', 'slug': 'fra.1', 'name': 'Ligue 1'},
        'eredivisie': {'sport': 'soccer', 'slug': 'ned.1', 'name': 'Eredivisie'},
        'primeira': {'sport': 'soccer', 'slug': 'por.1', 'name': 'Primeira Liga'},
        'championship': {'sport': 'soccer', 'slug': 'eng.2', 'name': 'Championship'},
        'nba': {'sport': 'basketball', 'slug': 'nba', 'name': 'NBA'}
    }

    def _fetch_from_url(self, url, params=None):
        try:
            response = requests.get(url, params=params)
            print(response.json())
            response.raise_for_status()
            return response.json()  
        except Exception:
            return {}

    def _get_api_url(self, league_code):
        config = self.LEAGUES_CONFIG.get(league_code)
        if not config:
            return None
        return f"http://site.api.espn.com/apis/site/v2/sports/{config['sport']}/{config['slug']}/scoreboard"

    def get_games(self, league_code='epl', type='upcoming', dates=None):
        if league_code == 'all':
             # Aggregate all leagues (expensive, but requested)
             all_games = []
             for code in self.LEAGUES_CONFIG.keys():
                 games = self._fetch_league_games(code, type, dates)
                 all_games.extend(games)
             
             # specific sort for aggregated list
             all_games.sort(key=lambda x: x['date'], reverse=(type == "past"))
             return all_games
        else:
             return self._fetch_league_games(league_code, type, dates)

    def _fetch_league_games(self, league_code, type, dates):
        url = self._get_api_url(league_code)
        if not url: return []
        
        all_events = []
        
        # If dates is provided, use it (single call)
        # If type is 'past', fetch last 4 weeks
        # If type is 'upcoming', fetch next 2 weeks (current week + next week)
        request_dates = []
        
        if dates:
            request_dates = [dates]
        elif type == "past":
            # Fetch last 30 days using range
            today = datetime.now()
            start = (today - timedelta(days=30)).strftime("%Y%m%d")
            end = today.strftime("%Y%m%d")
            request_dates = [f"{start}-{end}"]
        else: # upcoming
            # Fetch Current + Next 14 days using range
            today = datetime.now()
            start = today.strftime("%Y%m%d")
            end = (today + timedelta(days=14)).strftime("%Y%m%d")
            request_dates = [f"{start}-{end}"]

        for date_param in request_dates:
            params = {}
            if date_param:
                params['dates'] = date_param
            
            data = self._fetch_from_url(url, params)
            if not data: continue

            for event in data.get('events', []):
                game_info = self._process_event(event, league_code)
                if game_info:
                    all_events.append(game_info)

        # Remove duplicates if any (based on id)
        unique_events = {e['id']: e for e in all_events}.values()
        games = list(unique_events)
        
        # Sort by date
        games.sort(key=lambda x: x['date'], reverse=(type == "past"))

        if type == "upcoming":
            return [g for g in games if g['status'] in ['pre', 'in']]
        elif type == "past":
            return [g for g in games if g['status'] == 'post']
        
        return games

    def _process_event(self, event, league_code):
        try:
            status_id = event['status']['type']['state']
            
            competitors = event['competitions'][0]['competitors']
            home = next((c for c in competitors if c['homeAway'] == 'home'), None)
            away = next((c for c in competitors if c['homeAway'] == 'away'), None)
            
            if not home or not away: return None

            game_info = {
                'id': event['id'],
                'date': event['date'],
                'status': status_id,
                'status_detail': event['status']['type']['shortDetail'],
                'home_team': {
                    'name': home['team']['displayName'],
                    'logo': home['team'].get('logo', ''),
                    'score': home.get('score', '0'),
                    'winner': home.get('winner', False)
                },
                'away_team': {
                    'name': away['team']['displayName'],
                    'logo': away['team'].get('logo', ''),
                    'score': away.get('score', '0'),
                    'winner': away.get('winner', False)
                },
                'league': league_code,
                'league_name': self.LEAGUES_CONFIG[league_code]['name']
            }
            return game_info
            return game_info
        except Exception:
            return None

    def get_finished_game(self, event_id, league_code):
        # We need to know the sport/league to construct the URL
        # We can try to infer or pass it. 
        # For simplicity, we'll iterate configs or require league_code.
        url = self._get_api_url(league_code)
        if not url: return None
        
        # specific event endpoint usually: .../scoreboard/{id} but for dashboard we used params
        # ESPN site API usually allows filtering by id via 'events' param or just fetching scoreboard
        # Easiest: use the summary endpoint for one game
        # http://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
        
        config = self.LEAGUES_CONFIG.get(league_code)
        summary_url = f"http://site.api.espn.com/apis/site/v2/sports/{config['sport']}/{config['slug']}/summary"
        
        try:
            data = self._fetch_from_url(summary_url, params={'event': event_id})
            if not data or 'header' not in data: return None
            
            competitions = data['header']['competitions'][0]
            status = competitions['status']['type']['state'] # 'post' if finished
            
            if status != 'post':
                return {'status': status} # Not finished

            # Winner info
            competitors = competitions['competitors']
            home = next((c for c in competitors if c['homeAway'] == 'home'), {})
            away = next((c for c in competitors if c['homeAway'] == 'away'), {})
            
            return {
                'status': 'post',
                'home_score': int(home.get('score', 0)),
                'away_score': int(away.get('score', 0)),
                'winner': 'home' if home.get('winner') else ('away' if away.get('winner') else 'draw')
            }
        except Exception as e:
            print(f"Error fetching game result: {e}")
            return None
