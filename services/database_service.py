
import sqlite3
import json
import os
from datetime import datetime

class DatabaseService:
    DB_NAME = "safepick.db"

    def __init__(self):
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.DB_NAME)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                home_team TEXT,
                away_team TEXT,
                league TEXT,
                prediction_json TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Stats table (key-value store for simple counters)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_stats (
                param_key TEXT PRIMARY KEY,
                param_value INTEGER DEFAULT 0
            )
        ''')
        
        # Initialize default stats if not exist
        cursor.execute('INSERT OR IGNORE INTO site_stats (param_key, param_value) VALUES ("total_visits", 0)')
        cursor.execute('INSERT OR IGNORE INTO site_stats (param_key, param_value) VALUES ("total_predictions", 0)')
        
        conn.commit()
        conn.close()

    def save_prediction(self, match_data, prediction_result):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO predictions (match_id, home_team, away_team, league, prediction_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                match_data.get('id', 'unknown'),
                match_data.get('home_team'),
                match_data.get('away_team'),
                match_data.get('league'),
                json.dumps(prediction_result)
            ))
            
            # Increment total predictions count
            cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = "total_predictions"')
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"DB Error saving prediction: {e}")
            return False

    def increment_visit(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = "total_visits"')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error incrementing visit: {e}")

    def get_stats(self):
        try:
            with sqlite3.connect(self.DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT param_value FROM site_stats WHERE param_key='total_visits'")
                visits = c.fetchone()
                total_visits = int(visits[0]) if visits else 0
                
                c.execute("SELECT COUNT(*) FROM predictions")
                total_predictions = c.fetchone()[0]

                # Calculate Win Rate
                c.execute("SELECT COUNT(*) FROM predictions WHERE result='Win'")
                wins = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM predictions WHERE result IN ('Win', 'Loss')")
                total_results = c.fetchone()[0]
                
                win_rate = 0
                if total_results > 0:
                    win_rate = int((wins / total_results) * 100)

                return {
                    "total_visits": total_visits,
                    "total_predictions": total_predictions,
                    "win_rate": win_rate,
                    "total_graded": total_results
                }
        except Exception as e:
            print(f"DB Error fetching stats: {e}")
            return {"total_visits": 0, "total_predictions": 0, "win_rate": 0, "total_graded": 0}

    def update_prediction_result(self, prediction_id, result):
        try:
            with sqlite3.connect(self.DB_NAME) as conn:
                c = conn.cursor()
                c.execute("UPDATE predictions SET result = ? WHERE id = ?", (result, prediction_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"Error updating result: {e}")
            return False

    def get_recent_predictions(self, limit=10):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?', (limit,))
            columns = [col[0] for col in cursor.description]
            predictions = []
            for row in cursor.fetchall():
                pred = dict(zip(columns, row))
                # Parse the JSON string back to dict
                if pred.get('prediction_json'):
                    try:
                        pred['prediction_data'] = json.loads(pred['prediction_json'])
                    except:
                        pred['prediction_data'] = {}
                predictions.append(pred)
            conn.close()
            return predictions
        except Exception as e:
            print(f"DB Error fetching recent predictions: {e}")
            return []

    def get_pending_predictions(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Fetch predictions where result is NULL or empty
            cursor.execute("SELECT * FROM predictions WHERE result IS NULL OR result = ''")
            columns = [col[0] for col in cursor.description]
            predictions = []
            for row in cursor.fetchall():
                pred = dict(zip(columns, row))
                if pred.get('prediction_json'):
                    try:
                        pred['prediction_data'] = json.loads(pred['prediction_json'])
                    except:
                        pred['prediction_data'] = {}
                predictions.append(pred)
            conn.close()
            return predictions
        except Exception as e:
            print(f"DB Error fetching pending: {e}")
            return []

    def reset_database(self):
        try:
            with sqlite3.connect(self.DB_NAME) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM predictions")
                c.execute("UPDATE site_stats SET param_value = 0")
                conn.commit()
            return True
        except Exception as e:
            print(f"Error resetting DB: {e}")
            return False
