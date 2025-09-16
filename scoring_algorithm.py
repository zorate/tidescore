def get_score_suggestions(score_result):
    """Generate friendly suggestions based on score breakdown"""
    suggestions = []
    breakdown = score_result.get('breakdown', {})
    scaled_score = score_result.get('scaled_score', 0)
    
    # Personal & Employment suggestions
    if breakdown.get('Personal & Employment', 0) < 25:
        suggestions.append("✅ Improve your employment verification - provide better employment proof documents")
    
    # Airtime & Data suggestions
    if breakdown.get('Airtime & Data', 0) < 60:
        suggestions.append("📱 Increase your airtime spending consistency across all 3 months")
    
    # Bill Payments suggestions
    if breakdown.get('Bill Payments', 0) < 85:
        suggestions.append("💡 Add more verified bill payments (electricity, DSTV, internet, etc.)")
    
    # Bank Activity suggestions
    if breakdown.get('Bank Activity', 0) < 100:
        suggestions.append("🏦 Maintain higher average bank balance and consistent deposits")
    
    # Guarantors suggestions
    if breakdown.get('Guarantors', 0) < 45:
        suggestions.append("👥 Add more reliable guarantors with strong relationships")
    
    # Overall score suggestions
    if scaled_score < 250:
        suggestions.append("🚨 Your score is very high risk. Focus on improving all areas above.")
    elif scaled_score < 450:
        suggestions.append("⚠️  Medium risk score. Improve multiple areas for better rates.")
    elif scaled_score < 650:
        suggestions.append("👍 Good score! Minor improvements can get you to excellent range.")
    else:
        suggestions.append("🎉 Excellent score! You qualify for our best rates!")
    
    return suggestions

# Then modify your calculate_tidescore function to include suggestions:

def calculate_tidescore(verified_data):
    """
    Calculate TideScore based on the comprehensive methodology
    verified_data: Dictionary with all verified applicant information
    """
    max_possible_raw_score = 740
    
    # 1. Personal & Employment Information (Max: 50 points)
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

    # 2. Airtime & Data Consumption (Max: 120 points)
    def calculate_air_score(data):
        if data.get('airtime_status') in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
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

    # 3. Bill Payments (Max: 170 points)
    def calculate_bill_score(data):
        if data.get('bill_status') in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        verified_bills_count = sum([
            1 if data.get('electricity_verified') == 'Yes' else 0,
            1 if data.get('dstv_verified') == 'Yes' else 0,
            1 if data.get('internet_verified') == 'Yes' else 0,
            1 if data.get('water_verified') == 'Yes' else 0,
            1 if data.get('rent_verified') == 'Yes' else 0
        ])
        
        if verified_bills_count >= 4:
            score += 150
        elif verified_bills_count >= 3:
            score += 100
        elif verified_bills_count >= 2:
            score += 60
        elif verified_bills_count >= 1:
            score += 30
        
        if verified_bills_count >= 2 and data.get('bill_status') == 'Verified':
            score += 20
        
        return score

    # 4. P2P Transactions (Max: 110 points)
    def calculate_p2p_score(data):
        if data.get('p2p_status') in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        num_unique_verified_p2p = int(data.get('num_unique_verified_p2p', 0) or 0)
        
        if num_unique_verified_p2p >= 5:
            score += 80
        elif num_unique_verified_p2p >= 3:
            score += 50
        elif num_unique_verified_p2p >= 1:
            score += 20
        
        p2p_total_value = float(data.get('p2p_total_value', 0) or 0)
        if p2p_total_value >= 50000:
            score += 20
        
        if data.get('p2p_consistent_across_months') == 'Yes':
            score += 10
        
        return score

    # 5. Bank/Fintech Activity (Max: 200 points)
    def calculate_bank_score(data):
        if data.get('bank_status') in ['Unverified', 'Fraudulent']:
            return 0
        
        score = 0
        consistent_deposits_months = int(data.get('consistent_deposits_months', 0) or 0)
        
        if consistent_deposits_months >= 5:
            score += 100
        elif consistent_deposits_months >= 3:
            score += 60
        elif consistent_deposits_months >= 1:
            score += 20
        
        avg_monthly_balance = float(data.get('avg_monthly_balance', 0) or 0)
        if avg_monthly_balance >= 10000:
            score += 50
        elif avg_monthly_balance >= 5000:
            score += 30
        elif avg_monthly_balance >= 1000:
            score += 10
        
        if data.get('no_negative_flags') == 'Yes':
            score += 30
        
        return score

    # 6. Guarantors (Max: 90 points)
    def calculate_guarantor_score(data):
        score = 0
        g1_verified = data.get('g1_verified') == 'Yes'
        g2_verified = data.get('g2_verified') == 'Yes'
        
        if g1_verified and g2_verified:
            score += 70
        elif g1_verified or g2_verified:
            score += 30
        
        if g1_verified and data.get('g1_relationship') in ['Family Member', 'Religious Leader']:
            score += 10
        
        if g2_verified and data.get('g2_relationship') in ['Family Member', 'Religious Leader']:
            score += 10
        
        return score

    # 7. Penalties Calculation
    def calculate_penalties(data):
        penalty = 0
        airtime_status = data.get('airtime_status', 'Unverified')
        bill_status = data.get('bill_status', 'Unverified')
        p2p_status = data.get('p2p_status', 'Unverified')
        bank_status = data.get('bank_status', 'Unverified')
        g1_verified = data.get('g1_verified') == 'Yes'
        g2_verified = data.get('g2_verified') == 'Yes'
        
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

    # Main Calculation
    personal_score = calculate_personal_score(verified_data)
    air_score = calculate_air_score(verified_data)
    bill_score = calculate_bill_score(verified_data)
    p2p_score = calculate_p2p_score(verified_data)
    bank_score = calculate_bank_score(verified_data)
    guarantor_score = calculate_guarantor_score(verified_data)

    overall_raw_score_pre_penalties = personal_score + air_score + bill_score + p2p_score + bank_score + guarantor_score
    total_penalties = calculate_penalties(verified_data)

    final_raw_score = overall_raw_score_pre_penalties + total_penalties
    final_raw_score = max(0, final_raw_score)

    scaled_score = round((final_raw_score / max_possible_raw_score) * 850)

    # Risk Level
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

    final_result = {
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
        },
        "suggestions": get_score_suggestions({  # Pass the result to generate suggestions
            "scaled_score": scaled_score,
            "breakdown": {
                "Personal & Employment": personal_score,
                "Airtime & Data": air_score,
                "Bill Payments": bill_score,
                "Bank Activity": bank_score,
                "Guarantors": guarantor_score
            }
        })
    }
    
    return final_result