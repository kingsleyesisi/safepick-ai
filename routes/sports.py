
from flask import Blueprint, render_template, request, jsonify
from services.sports_service import SportsService
from services.gemini_service import GeminiService
from services.database_service import DatabaseService

sports_bp = Blueprint('sports', __name__)
sports_service = SportsService()
gemini_service = GeminiService()
db_service = DatabaseService()

@sports_bp.route('/')
def index():
    # Track visit
    db_service.increment_visit()
    
    league = request.args.get('league', 'all') # Default to All
    games_data = sports_service.get_games(league_code=league, type='upcoming')
    
    # If it's a dict (split), unpack. If legacy list (shouldn't be for upcoming), handle.
    if isinstance(games_data, dict):
        live_games = games_data.get('live', [])
        upcoming_games = games_data.get('upcoming', [])
    else:
        live_games = []
        upcoming_games = games_data
        
    return render_template('sports_index.html', 
                         live_games=live_games, 
                         upcoming_games=upcoming_games, 
                         active_league=league)

@sports_bp.route('/history')
def history():
    league = request.args.get('league', 'all')
    games = sports_service.get_games(league_code=league, type='past')
    return render_template('sports_history.html', games=games, active_league=league)

@sports_bp.route('/result/update', methods=['POST'])
def update_result():
    data = request.json
    pred_id = data.get('id')
    result = data.get('result') # 'Win', 'Loss', 'Void'
    
    if db_service.update_prediction_result(pred_id, result):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update"}), 500

@sports_bp.route('/stats')
def stats():
    stats_data = db_service.get_stats()
    # Fetch pending/graded predictions separately if needed, for now just recent
    recent_predictions = db_service.get_recent_predictions(limit=50) 
    return render_template('stats.html', stats=stats_data, predictions=recent_predictions)


@sports_bp.route('/stats/reset', methods=['POST'])
def reset_stats():
    if db_service.reset_database():
        return jsonify({"success": True})
    return jsonify({"error": "Failed"}), 500

@sports_bp.route('/stats/check-results', methods=['POST'])
def check_results():
    import concurrent.futures
    
    pending = db_service.get_pending_predictions()
    if not pending:
        return jsonify({"updated": 0})
    
    updated_count = 0
    
    def grade_single_prediction(pred):
        """Fetch and grade a single prediction efficiently"""
        try:
            match_id = pred.get('match_id')
            league = pred.get('league')
            p_data = pred.get('prediction_data', {})
            struc = p_data.get('structured_prediction')
            
            if not struc or not match_id or not league:
                return None
            
            # Directly fetch this specific game
            game_result = None
            
            if league and league != 'all':
                game_result = sports_service.get_finished_game(match_id, league)
            else:
                # If league is 'all' or missing, we must search all leagues for this ID
                # Iterate through all configured leagues
                # This is acceptable because it's only for specific single IDs, not a full history fetch
                for code in sports_service.LEAGUES_CONFIG.keys():
                    res = sports_service.get_finished_game(match_id, code)
                    if res:
                        game_result = res
                        break
            
            if not game_result or game_result.get('status') != 'post':
                return None  # Game not finished yet
            
            # Extract scores
            h_score = game_result.get('home_score', 0)
            a_score = game_result.get('away_score', 0)
            
            # Determine result based on market type
            result = 'Void'
            market_type = struc.get('market_type')
            
            if market_type == 'moneyline' or struc.get('type') == 'winner':
                actual_winner = game_result.get('winner')  # 'home', 'away', 'draw'
                selection = struc.get('selection', struc.get('target', '')).lower()
                
                if selection == actual_winner:
                    result = 'Win'
                elif actual_winner == 'draw':
                    result = 'Win' if selection == 'draw' else 'Loss'
                else:
                    result = 'Loss'
                    
            elif market_type == 'over_under':
                total = h_score + a_score
                line = float(struc.get('line', 0))
                direction = struc.get('selection', '').lower()
                
                if direction == 'over':
                    result = 'Win' if total > line else 'Loss'
                elif direction == 'under':
                    result = 'Win' if total < line else 'Loss'
                    
            elif market_type == 'double_chance':
                actual_winner = game_result.get('winner')
                sel = struc.get('selection', '').upper()
                
                if sel == '1X':
                    result = 'Win' if actual_winner in ['home', 'draw'] else 'Loss'
                elif sel == 'X2':
                    result = 'Win' if actual_winner in ['away', 'draw'] else 'Loss'
                elif sel == '12':
                    result = 'Win' if actual_winner in ['home', 'away'] else 'Loss'
            
            # Update if we got a valid result
            if result in ['Win', 'Loss', 'Void']:
                db_service.update_prediction_result(pred['id'], result)
                print(f"✓ Graded {match_id}: {result} (Score: {h_score}-{a_score})")
                return 1
            
            return None
            
        except Exception as e:
            print(f"Error grading prediction {pred.get('id')}: {e}")
            return None
    
    # Process all predictions concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(grade_single_prediction, pending)
        updated_count = sum(r for r in results if r)
    
    return jsonify({"updated": updated_count})
        
@sports_bp.route('/predict', methods=['POST'])
def predict():
    data = request.json
    home = data.get('home_team')
    away = data.get('away_team')
    league = data.get('league')
    event_id = data.get('event_id')
    device = data.get('device', 'Unknown')
    
    if not home or not away:
        return jsonify({'error': 'Missing team data'}), 400
        
    prediction = gemini_service.get_prediction(home, away, league)
    
    # Store prediction in DB if successful
    if prediction and 'error' not in prediction:
        match_data = {
            "id": event_id if event_id else f"{home}-{away}-{league}", 
            "home_team": home,
            "away_team": away,
            "league": league,
            "device": device
        }
        db_service.save_prediction(match_data, prediction)
        
    return jsonify(prediction)

@sports_bp.route('/game/<league>/<event_id>/stats')
def get_game_stats(league, event_id):
    stats = sports_service.get_game_stats(event_id, league)
    if not stats:
        return jsonify({'error': 'Stats not found'}), 404
    return jsonify(stats)
