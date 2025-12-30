import json
from datetime import date
from services.db import get_cursor

def calculate_daily_score(target_date: date):
    """
    The Judge.
    Reads immutable logs -> Applies Config Rules -> Writes Derived Score.
    """
    date_iso = target_date.isoformat()
    
    with get_cursor(commit=True) as c:
        # 1. Fetch Raw Truth (Logs)
        c.execute("SELECT * FROM daily_logs WHERE date = ?", (date_iso,))
        logs = c.fetchone()
        if not logs:
            return None # No logs yet, cannot score

        # 2. Fetch The Law (Active Config)
        c.execute("""
            SELECT sc.nps_weights, sc.veto_thresholds, sc.id as config_id
            FROM daily_config_routing dcr
            JOIN system_config sc ON dcr.config_id = sc.id
            WHERE dcr.date = ?
        """, (date_iso,))
        config = c.fetchone()
        
        weights = json.loads(config['nps_weights'])
        vetoes = json.loads(config['veto_thresholds'])

        # 3. Calculate Domain Scores (0-100)
        
        # ENGINE: Plan Hit Rate (Already calculated in plan_service, but we need it here)
        # We re-query the plan service logic raw here for speed/atomic transaction
        c.execute("""
            SELECT COUNT(*) as total, 
            SUM(CASE WHEN completion_status = 'COMPLETE' THEN 1 ELSE 0 END) as completed 
            FROM daily_plan WHERE date = ?
        """, (date_iso,))
        plan_data = c.fetchone()
        score_engine = 0.0
        if plan_data['total'] > 0:
            score_engine = (plan_data['completed'] / plan_data['total']) * 100.0

        # VESSEL: Sleep & Alcohol
        # Simple Logic: Sleep > 7h = 100, else decay. Alcohol > 0 = 0.
        score_vessel = 100.0
        if logs['sleep_score'] < 70: score_vessel -= (70 - logs['sleep_score']) * 2
        if logs['alcohol_units'] > 0: score_vessel -= 50 # Heavy penalty
        score_vessel = max(0.0, score_vessel)

        # RESOURCES: Spend
        # Simple Logic: Spend > 100 = 0? Need a limit. 
        # For v0.1: If spend > 50, score drops.
        score_resources = 100.0
        if logs['total_spend'] > 50: score_resources = 50.0 # Binary punishment for now
        
        # SYSTEM: Screen Time & Completeness
        score_system = 100.0
        if logs['screen_time_mins'] > 120: score_system = 50.0

        # 4. The NPS Calculation
        raw_score = (
            (score_engine * weights['engine']) +
            (score_vessel * weights['vessel']) +
            (score_resources * weights['resources']) +
            (score_system * weights['system'])
        )

        # 5. The Veto (Safety Multiplier)
        safety_mult = 1.0
        if logs['alcohol_units'] > vetoes['alcohol_units']: safety_mult = 0.0
        if logs['sleep_score'] < (vetoes['sleep_min'] * 10): safety_mult = 0.5 # Scale mismatch fix later

        final_nps = raw_score * safety_mult

        # 6. Write to Scoreboard (Append Only)
        c.execute("""
            INSERT INTO daily_derived_log 
            (date, config_id, score_engine, score_vessel, score_resources, score_system, nps_score, safety_multiplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_iso, config['config_id'], score_engine, score_vessel, score_resources, score_system, final_nps, safety_mult))
        
        return final_nps