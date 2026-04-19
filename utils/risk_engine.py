import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# BUG-018 FIX: Graceful fallback if fuzzywuzzy/rapidfuzz is not installed.
# Prefer rapidfuzz (faster, actively maintained) over the legacy fuzzywuzzy.
try:
    from rapidfuzz import fuzz
except ImportError:
    try:
        from fuzzywuzzy import fuzz
    except ImportError:
        fuzz = None
        logger.warning("Neither rapidfuzz nor fuzzywuzzy is installed. Fuzzy duplicate detection is disabled.")

def detect_duplicate_voter(app_data, mongo):
    """
    Detects potential duplicate voters based on ID Proof, Phone, and Profile Similarity.
    """
    risk_report = {
        "duplicate_type": "Unique",
        "reason": "New Registration",
        "confidence": 0,
        "action": "Allow",
        "details": []
    }

    # 1. Exact Match: ID Proof Number (High Risk)
    existing_id = mongo.db.applications.find_one({
        "id_proof_number": app_data.get('id_proof_number'),
        "status": {"$ne": "Rejected"} # Don't block if previous was rejected (unless for fraud)
    })
    
    if existing_id:
        risk_report.update({
            "duplicate_type": "Exact",
            "reason": f"Same ID Proof Number found (App ID: {str(existing_id['_id'])[-6:]})",
            "confidence": 100,
            "action": "Block"
        })
        return risk_report

    # 2. Exact Match: Phone Number (Medium Risk)
    # Check if phone exists with DIFFERENT user_id
    existing_phone = mongo.db.applications.find_one({
        "phone": app_data.get('phone'),
        "user_id": {"$ne": app_data.get('user_id')},
        "status": {"$ne": "Rejected"}
    })

    if existing_phone:
        if fuzz is None:
            # Fuzzy library unavailable — flag for manual review
            risk_report.update({
                "duplicate_type": "Possible",
                "reason": "Phone number reused (fuzzy matching unavailable)",
                "confidence": 60,
                "action": "Review"
            })
        else:
            name_score = fuzz.ratio(
                app_data.get('full_name', '').lower(),
                existing_phone.get('full_name', '').lower()
            )
            if name_score > 85:
                risk_report.update({
                    "duplicate_type": "High Probability",
                    "reason": "Same Phone & Similar Name",
                    "confidence": 90,
                    "action": "Block"
                })
                return risk_report
            else:
                risk_report.update({
                    "duplicate_type": "Possible",
                    "reason": "Phone number reused by different person",
                    "confidence": 60,
                    "action": "Review"
                })

    # 3. AI Similar Profile Detection (Fuzzy Match)
    if fuzz is not None:
        potential_matches = mongo.db.applications.find({
            "pin_code": app_data.get('pin_code'),
            "user_id": {"$ne": app_data.get('user_id')},
            "status": {"$ne": "Rejected"}
        })

        max_score = 0
        best_match_id = None

        for match in potential_matches:
            score = 0
            name_sim = fuzz.token_sort_ratio(app_data.get('full_name', ''), match.get('full_name', ''))
            score += name_sim * 0.4
            if app_data.get('dob') == match.get('dob'):
                score += 30
            addr_sim = fuzz.token_set_ratio(app_data.get('present_address', ''), match.get('present_address', ''))
            score += addr_sim * 0.2
            rel_sim = fuzz.token_sort_ratio(app_data.get('relative_name', ''), match.get('relative_name', ''))
            score += rel_sim * 0.1
            if score > max_score:
                max_score = score
                best_match_id = match['_id']

        if max_score > 75:
            if risk_report['action'] == "Review" and max_score > 85:
                risk_report.update({
                    "duplicate_type": "Confirmed Profile Match",
                    "reason": f"Same Phone + Similar Profile (Score: {int(max_score)}%)",
                    "confidence": int(max_score),
                    "action": "Block"
                })
            elif risk_report['action'] == "Allow":
                risk_report.update({
                    "duplicate_type": "Profile Match",
                    "reason": f"Similar Profile found (Score: {int(max_score)}%)",
                    "confidence": int(max_score),
                    "action": "Review" if max_score < 90 else "Block"
                })

    return risk_report

def assess_fraud_risk(app_data, mongo):
    """
    Evaluates fraud risk based on patterns.
    """
    indicators = []
    risk_score = 0
    
    # 1. Age Anomalies
    dob = app_data.get('dob')
    if dob:
        try:
            # Handle string format if passed as string
            if isinstance(dob, str):
                birth_date = datetime.strptime(dob, '%Y-%m-%d')
            else:
                birth_date = dob # Assuming datetime object
                
            age = (datetime.now() - birth_date).days / 365.25
            if age < 18:
                indicators.append("Underage Applicant")
                risk_score += 100 # Immediate Block
            elif age > 120:
                indicators.append("Unrealistic Age (>120)")
                risk_score += 50
        except:
            pass

    # 2. Rapid Multiple Registrations
    # Check if ANY application exists from this user in last 2 minutes
    recent_app = mongo.db.applications.find_one({
        "user_id": app_data.get('user_id'),
        "submitted_at": {"$gte": datetime.utcnow() - timedelta(minutes=2)}
    })
    if recent_app:
        indicators.append("Multiple submissions in short duration")
        risk_score += 40

    # Determine Risk Level
    risk_level = "Low"
    action = "Allow"
    
    if risk_score >= 80:
        risk_level = "High"
        action = "Block"
    elif risk_score >= 40:
        risk_level = "Medium"
        action = "Review"
        
    return {
        "risk_level": risk_level,
        "indicators": indicators,
        "risk_score": risk_score,
        "action": action
    }
