
import requests
from datetime import datetime, timedelta
import concurrent.futures

class SportsService:
    # Configuration for supported leagues and their ESPN paths
    LEAGUES_CONFIG = {
        'epl': {'sport': 'soccer', 'slug': 'eng.1', 'name': 'Premier League'},
        'laliga': {'sport': 'soccer', 'slug': 'esp.1', 'name': 'La Liga'},
        'bundesliga': {'sport': 'soccer', 'slug': 'ger.1', 'name': 'Bundesliga'},
        'seriea': {'sport': 'soccer', 'slug': 'ita.1', 'name': 'Serie A'},
        'ligue1': {'sport': 'soccer', 'slug': 'fra.1', 'name': 'Ligue 1'},
        'ucl': {'sport': 'soccer', 'slug': 'uefa.champions', 'name': 'Champions League'},
        'europa': {'sport': 'soccer', 'slug': 'uefa.europa', 'name': 'Europa League'},
        'afcon': {'sport': 'soccer', 'slug': 'caf.nations', 'name': 'AFCON'},
        'worldcup': {'sport': 'soccer', 'slug': 'fifa.world', 'name': 'World Cup'},
        'mls': {'sport': 'soccer', 'slug': 'usa.1', 'name': 'MLS'},
        'brasileiro': {'sport': 'soccer', 'slug': 'bra.1', 'name': 'Brasileirão'},
        'saudi': {'sport': 'soccer', 'slug': 'sau.1', 'name': 'Saudi Pro League'},
        'championship': {'sport': 'soccer', 'slug': 'eng.2', 'name': 'Championship'},
        'nba': {'sport': 'basketball', 'slug': 'nba', 'name': 'NBA'}
    }

    def _fetch_from_url(self, url, params=None):
        try:
            response = requests.get(url, params=params)
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
        all_games = []
        if league_code == 'all':
             # Aggregate all leagues (expensive, but requested)
             with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                 # Submit all tasks
                 future_to_code = {executor.submit(self._fetch_league_games, code, type, dates): code for code in self.LEAGUES_CONFIG.keys()}
                 
                 for future in concurrent.futures.as_completed(future_to_code):
                     try:
                         games = future.result()
                         all_games.extend(games)
                     except Exception as exc:
                         print(f"League fetching generated an exception: {exc}")
        else:
             all_games = self._fetch_league_games(league_code, type, dates)
        
        # Sort by date
        all_games.sort(key=lambda x: x['date'], reverse=(type == "past"))

        if type == "upcoming":
            # Split into Live and Upcoming
            live_games = [g for g in all_games if g['status'] == 'in']
            upcoming_games = [g for g in all_games if g['status'] == 'pre']
            
            # Sort upcoming by nearest time (already sorted by date above, but ensures asc)
            # live games also sorted by start time
            
            # live games also sorted by start time

            return {
                'live': live_games,
                'upcoming': upcoming_games
            }
        
        return all_games

    def get_game_stats(self, event_id):
        # We need to find the specific event details. 
        # Since we might not have the league context easily, we can try a general search or specific endpoint if we knew sport.
        # However, usually we pass league/sport from frontend. 
        # For now, let's assume valid ID works on the generic summary endpoint if we knew the sport.
        # We'll try to guess sport or iterate or ask frontend to pass league.
        # Let's rely on frontend passing league to index, maybe we can accept it here? 
        # Actually, ESPN summary endpoint structure is: sports/{sport}/{league}/summary?event={id}
        # If we don't know sport/league, we can't build URL easily without mapping event_id > league.
        # BUT: The user will click from a known league context usually.
        # Let's try to pass league_code if possible. If not, this is tricky. 
        # We'll modify the signature to accept league_code (optional).
        pass 

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
            # Fetch last 90 days using range to catch older pending predictions
            today = datetime.now()
            start = (today - timedelta(days=90)).strftime("%Y%m%d")
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

    def get_game_stats(self, event_id, league_code):
        url = self._get_api_url(league_code)
        if not url: return None
        
        config = self.LEAGUES_CONFIG.get(league_code)
        summary_url = f"http://site.api.espn.com/apis/site/v2/sports/{config['sport']}/{config['slug']}/summary"
        
        try:
            data = self._fetch_from_url(summary_url, params={'event': event_id})
            if not data: return None
            
            # Extract basic info
            header = data.get('header', {})
            comps = header.get('competitions', [{}])[0]
            competitors = comps.get('competitors', [])
            
            home = next((c for c in competitors if c['homeAway'] == 'home'), {})
            away = next((c for c in competitors if c['homeAway'] == 'away'), {})
            
            stats = {
                'time': comps.get('status', {}).get('type', {}).get('detail', 'N/A'),
                'score': f"{home.get('score','0')} - {away.get('score','0')}",
                'home_team': {'name': home.get('team',{}).get('displayName'), 'logo': home.get('team',{}).get('logo')},
                'away_team': {'name': away.get('team',{}).get('displayName'), 'logo': away.get('team',{}).get('logo')},
                'stats': []
            }

            # Extract Box Score / Match Stats
            boxscore = data.get('boxscore', {})
            teams = boxscore.get('teams', [])
            
            if teams:
                # Create a map for easy access
                stat_map = {}
                for t in teams:
                     tm = t.get('team', {})
                     t_stats = t.get('statistics', [])
                     # Flatten stats
                     for stat in t_stats:
                         label = stat['label'] # e.g. "Possession"
                         val = stat['displayValue']
                         
                         if label not in stat_map:
                             stat_map[label] = {'home': '-', 'away': '-'}
                             
                         # Identify if this is home or away stats
                         if tm.get('id') == home.get('id'):
                             stat_map[label]['home'] = val
                         else:
                             stat_map[label]['away'] = val
                
                # Convert map to list
                for label, vals in stat_map.items():
                    stats['stats'].append({
                        'label': label,
                        'home': vals['home'],
                        'away': vals['away']
                    })
                    
            return stats

        except Exception as e:
            print(f"Error stats: {e}")
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
