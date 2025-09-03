# scoring_algorithm.py

def calculate_tidescore_v2(applicant_data):
    """
    Enhanced TideScore algorithm - More refined and structured version
    """
    max_possible_raw_score = 740

    # --- Helper Functions for Score Calculation ---
    def calculate_personal_score(data):
        score = 0
        if data.get('employment_verified') == 'Yes':
            employment_status = data.get('employment_status', '')
            if employment_status == "Employed (Full-time)":
                score += 20
            elif employment_status == "Self-Employed (Business Owner)":
                score += 15
            elif employment_status == "Employed (Part-time)":
                score += 10
            elif employment_status == "Student":
                score += 5
        
        if data.get('residency_verified') == 'Yes':
            score += 10
        
        education_level = data.get('education_level', '')
        if education_level in ["HND/B.Sc", "Masters", "PhD"]:
            score += 10
        elif education_level in ["OND/NCE", "Secondary School"]:
            score += 5
        
        return score

    def calculate_air_score(data):
        airtime_status = data.get('airtime_status', 'Unverified')
        if airtime_status in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        # Handle None values by converting to 0
        airtime_spend_m1 = float(data.get('airtime_spend_m1', 0) or 0)
        airtime_spend_m2 = float(data.get('airtime_spend_m2', 0) or 0)
        airtime_spend_m3 = float(data.get('airtime_spend_m3', 0) or 0)
        total_spend = airtime_spend_m1 + airtime_spend_m2 + airtime_spend_m3
        
        if total_spend >= 15000:
            score += 100
        elif total_spend >= 10000:
            score += 75
        elif total_spend >= 5000:
            score += 50
        elif total_spend >= 2000:
            score += 20
        
        if airtime_spend_m1 > 0 and airtime_spend_m2 > 0 and airtime_spend_m3 > 0:
            score += 20
        
        return score

    def calculate_bill_score(data):
        bill_status = data.get('bill_status', 'Unverified')
        if bill_status in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        verified_bills_count = sum([
            1 if data.get('electricity_verified') == 'on' else 0,
            1 if data.get('dstv_verified') == 'on' else 0,
            1 if data.get('internet_verified') == 'on' else 0,
            1 if data.get('water_verified') == 'on' else 0,
            1 if data.get('rent_verified') == 'on' else 0
        ])
        
        if verified_bills_count >= 4:
            score += 150
        elif verified_bills_count >= 3:
            score += 100
        elif verified_bills_count >= 2:
            score += 60
        elif verified_bills_count >= 1:
            score += 30
        
        if verified_bills_count >= 2 and bill_status == 'Verified':
            score += 20
        
        return score

    def calculate_p2p_score(data):
        p2p_status = data.get('p2p_status', 'Unverified')
        if p2p_status in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        # Handle None values by converting to 0
        num_unique_verified_p2p = int(data.get('num_unique_verified_p2p', 0) or 0)
        
        if num_unique_verified_p2p >= 5:
            score += 80
        elif num_unique_verified_p2p >= 3:
            score += 50
        elif num_unique_verified_p2p >= 1:
            score += 20
        
        # Handle None values by converting to 0
        p2p_total_value = float(data.get('p2p_total_value', 0) or 0)
        if p2p_total_value >= 50000:
            score += 20
        
        if data.get('p2p_consistent_across_months') == 'on':
            score += 10
        
        return score

    def calculate_bank_score(data):
        bank_status = data.get('bank_status', 'Unverified')
        if bank_status in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        # Handle None values by converting to 0
        consistent_deposits_months = int(data.get('consistent_deposits_months', 0) or 0)
        
        if consistent_deposits_months >= 5:
            score += 100
        elif consistent_deposits_months >= 3:
            score += 60
        elif consistent_deposits_months >= 1:
            score += 20
        
        # Handle None values by converting to 0
        avg_monthly_balance = float(data.get('avg_monthly_balance', 0) or 0)
        if avg_monthly_balance >= 10000:
            score += 50
        elif avg_monthly_balance >= 5000:
            score += 30
        elif avg_monthly_balance >= 1000:
            score += 10
        
        if data.get('no_negative_flags') == 'on':
            score += 30
        
        return score

    def calculate_guarantor_score(data):
        score = 0
        g1_verified = data.get('g1_verified') == 'on'
        g2_verified = data.get('g2_verified') == 'on'
        
        if g1_verified and g2_verified:
            score += 70
        elif g1_verified or g2_verified:
            score += 30
        
        if g1_verified and data.get('g1_relationship') in ['Family Member', 'Religious Leader']:
            score += 10
        
        if g2_verified and data.get('g2_relationship') in ['Family Member', 'Religious Leader']:
            score += 10
        
        return score

    def calculate_penalties(data):
        penalty = 0
        airtime_status = data.get('airtime_status', 'Unverified')
        bill_status = data.get('bill_status', 'Unverified')
        p2p_status = data.get('p2p_status', 'Unverified')
        bank_status = data.get('bank_status', 'Unverified')
        g1_verified = data.get('g1_verified') == 'on'
        g2_verified = data.get('g2_verified') == 'on'
        
        if airtime_status in ['Unverified', 'Fraudulent']:
            penalty -= 10
        if bill_status in ['Unverified', 'Fraudulent']:
            penalty -= 15
        if p2p_status in ['Unverified', 'Fraudulent']:
            penalty -= 20
        if not g1_verified and not g2_verified:
            penalty -= 25
        if bank_status in ['Unverified', 'Fraudulent']:
            penalty -= 30
        
        return penalty

    # --- Main Calculation Logic ---
    personal_score = calculate_personal_score(applicant_data)
    air_score = calculate_air_score(applicant_data)
    bill_score = calculate_bill_score(applicant_data)
    p2p_score = calculate_p2p_score(applicant_data)
    bank_score = calculate_bank_score(applicant_data)
    guarantor_score = calculate_guarantor_score(applicant_data)

    overall_raw_score_pre_penalties = personal_score + air_score + bill_score + p2p_score + bank_score + guarantor_score
    total_penalties = calculate_penalties(applicant_data)

    final_raw_score = overall_raw_score_pre_penalties + total_penalties
    final_raw_score = max(0, final_raw_score)  # Ensure not negative

    scaled_score = round((final_raw_score / max_possible_raw_score) * 850)

    # Determine risk level
    if scaled_score >= 650:
        risk_level = "Low"
    elif scaled_score >= 450:
        risk_level = "Medium"
    elif scaled_score >= 250:
        risk_level = "High"
    else:
        risk_level = "Very High"

    return {
        "scaled_score": scaled_score,
        "risk_level": risk_level,
        "breakdown": {
            "Personal & Employment": personal_score,
            "Airtime & Data": air_score,
            "Bill Payments": bill_score,
            "P2P Transactions": p2p_score,
            "Bank Activity": bank_score,
            "Guarantors": guarantor_score,
            "Total Penalties": total_penalties,
            "Final Raw Score": final_raw_score,
            "Overall Raw Score (Pre-Penalties)": overall_raw_score_pre_penalties
        }
    }