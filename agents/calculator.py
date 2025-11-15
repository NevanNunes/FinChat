"""Financial Calculator - SIP, EMI, Retirement calculations"""
import logging
from typing import Dict, Any
from config import *

logger = logging.getLogger(__name__)

class FinancialCalculator:

    @staticmethod
    def _validate_positive(value: float, name: str) -> None:
        """Validate that a value is positive"""
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")

    @staticmethod
    def _validate_percentage(value: float, name: str) -> None:
        """Validate that a percentage is reasonable (0-100%)"""
        if not (0 <= value <= 1):
            raise ValueError(f"{name} must be between 0 and 1 (as decimal), got {value}")

    @staticmethod
    def _validate_age(age: int, name: str) -> None:
        """Validate that age is reasonable"""
        if not (0 < age < 120):
            raise ValueError(f"{name} must be between 0 and 120, got {age}")

    @staticmethod
    def sip_returns(
        monthly_sip: float,
        years: int,
        expected_return: float = None
    ) -> Dict[str, Any]:
        """Calculate SIP returns with validation using config defaults"""
        if expected_return is None:
            expected_return = DEFAULT_SIP_RETURN

        # Input validation
        try:
            FinancialCalculator._validate_positive(monthly_sip, "Monthly SIP")
            FinancialCalculator._validate_positive(years, "Investment years")
            FinancialCalculator._validate_percentage(expected_return, "Expected return")

            if years > SIP_MAX_YEARS:
                raise ValueError(f"Investment period cannot exceed {SIP_MAX_YEARS} years")

        except ValueError as e:
            logger.error(f"SIP validation failed: {e}")
            return {"error": str(e)}

        logger.info(f"Calculating SIP: ₹{monthly_sip}/month for {years} years at {expected_return*100}%")

        months = years * 12
        monthly_rate = expected_return / 12
        maturity_value = monthly_sip * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
        total_invested = monthly_sip * months
        gains = maturity_value - total_invested

        # Year-by-year breakdown for visualization
        yearly_breakdown = []
        for year in range(1, years + 1):
            m = year * 12
            value = monthly_sip * (((1 + monthly_rate) ** m - 1) / monthly_rate) * (1 + monthly_rate)
            invested = monthly_sip * m
            gain = value - invested
            yearly_breakdown.append({
                "year": year,
                "invested": round(invested, 0),
                "value": round(value, 0),
                "gains": round(gain, 0)
            })

        return {
            "monthly_sip": monthly_sip,
            "years": years,
            "investment_period": f"{years} years",
            "expected_return": expected_return,
            "expected_return_display": f"{expected_return*100:.1f}%",
            "total_invested": round(total_invested, 0),
            "maturity_amount": round(maturity_value, 0),
            "gains": round(gains, 0),
            "returns_percentage": round((gains / total_invested) * 100, 2),
            "calculation_breakdown": {
                "step1_monthly_sip": monthly_sip,
                "step2_total_months": months,
                "step3_monthly_rate": round(monthly_rate * 100, 4),
                "step4_total_invested": round(total_invested, 0),
                "step5_maturity_value": round(maturity_value, 0),
                "step6_total_gains": round(gains, 0),
                "step7_returns_percent": round((gains / total_invested) * 100, 2)
            },
            "yearly_breakdown": yearly_breakdown,
            "milestones": {
                "year_5": yearly_breakdown[4] if years >= 5 else None,
                "year_10": yearly_breakdown[9] if years >= 10 else None,
                "year_15": yearly_breakdown[14] if years >= 15 else None,
                "year_20": yearly_breakdown[19] if years >= 20 else None
            }
        }

    @staticmethod
    def emi_calculator(
        loan_amount: float,
        interest_rate: float = None,
        tenure_years: int = 20
    ) -> Dict[str, Any]:
        """Calculate EMI for loan with validation using config defaults"""
        if interest_rate is None:
            interest_rate = DEFAULT_EMI_INTEREST

        # Input validation
        try:
            FinancialCalculator._validate_positive(loan_amount, "Loan amount")
            FinancialCalculator._validate_positive(interest_rate, "Interest rate")
            FinancialCalculator._validate_positive(tenure_years, "Tenure")

            if interest_rate > EMI_MAX_INTEREST:
                raise ValueError(f"Interest rate cannot exceed {EMI_MAX_INTEREST}%")
            if tenure_years > EMI_MAX_TENURE:
                raise ValueError(f"Tenure cannot exceed {EMI_MAX_TENURE} years")
            if loan_amount > EMI_MAX_LOAN:
                raise ValueError(f"Loan amount cannot exceed ₹{EMI_MAX_LOAN:,.0f}")

        except ValueError as e:
            logger.error(f"EMI validation failed: {e}")
            return {"error": str(e)}

        logger.info(f"Calculating EMI: ₹{loan_amount} at {interest_rate}% for {tenure_years} years")

        monthly_rate = interest_rate / 12 / 100
        months = tenure_years * 12

        if monthly_rate == 0:
            emi = loan_amount / months
        else:
            emi = loan_amount * monthly_rate * ((1 + monthly_rate) ** months) / (((1 + monthly_rate) ** months) - 1)

        total_payment = emi * months
        total_interest = total_payment - loan_amount

        # Year-by-year amortization schedule for visualization
        yearly_breakdown = []
        remaining_principal = loan_amount

        for year in range(1, tenure_years + 1):
            year_principal = 0
            year_interest = 0

            # Calculate for 12 months in this year
            for month in range(12):
                if remaining_principal > 0:
                    month_interest = remaining_principal * monthly_rate
                    month_principal = emi - month_interest
                    year_principal += month_principal
                    year_interest += month_interest
                    remaining_principal -= month_principal

            yearly_breakdown.append({
                "year": year,
                "principal_paid": round(year_principal, 0),
                "interest_paid": round(year_interest, 0),
                "total_paid": round(year_principal + year_interest, 0),
                "remaining_balance": round(max(0.0, remaining_principal), 0)
            })

        # Calculate principal vs interest percentage
        principal_percentage = (loan_amount / total_payment) * 100
        interest_percentage = (total_interest / total_payment) * 100

        return {
            "loan_amount": loan_amount,
            "interest_rate": interest_rate,
            "interest_rate_display": f"{interest_rate}%",
            "tenure": f"{tenure_years} years",
            "tenure_years": tenure_years,
            "tenure_months": months,
            "monthly_emi": round(emi, 0),
            "total_payment": round(total_payment, 0),
            "total_interest": round(total_interest, 0),
            "principal_percentage": round(principal_percentage, 2),
            "interest_percentage": round(interest_percentage, 2),
            "calculation_breakdown": {
                "step1_loan_amount": loan_amount,
                "step2_monthly_interest_rate": round(monthly_rate * 100, 4),
                "step3_total_months": months,
                "step4_monthly_emi": round(emi, 0),
                "step5_total_payment": round(total_payment, 0),
                "step6_total_interest": round(total_interest, 0),
                "step7_interest_to_principal_ratio": round(total_interest / loan_amount, 2)
            },
            "yearly_breakdown": yearly_breakdown,
            "milestones": {
                "year_1": yearly_breakdown[0] if tenure_years >= 1 else None,
                "year_5": yearly_breakdown[4] if tenure_years >= 5 else None,
                "year_10": yearly_breakdown[9] if tenure_years >= 10 else None,
                "year_15": yearly_breakdown[14] if tenure_years >= 15 else None,
                "year_20": yearly_breakdown[19] if tenure_years >= 20 else None
            },
            "summary": {
                "first_year_principal": yearly_breakdown[0]["principal_paid"] if yearly_breakdown else 0,
                "first_year_interest": yearly_breakdown[0]["interest_paid"] if yearly_breakdown else 0,
                "last_year_principal": yearly_breakdown[-1]["principal_paid"] if yearly_breakdown else 0,
                "last_year_interest": yearly_breakdown[-1]["interest_paid"] if yearly_breakdown else 0
            }
        }

    @staticmethod
    def retirement_corpus(
        current_age: int,
        retirement_age: int,
        monthly_expense: float,
        inflation: float = None,
        post_retirement_years: int = None,
        sip_return: float = None,
        post_ret_return: float = None
    ) -> Dict[str, Any]:
        """Calculate retirement corpus with validation using code defaults"""
        # Use defaults from config
        if inflation is None:
            inflation = DEFAULT_INFLATION
        if post_retirement_years is None:
            post_retirement_years = DEFAULT_POST_RET_YEARS
        if sip_return is None:
            sip_return = DEFAULT_SIP_RETURN
        if post_ret_return is None:
            post_ret_return = DEFAULT_POST_RET_RETURN

        # Input validation
        try:
            FinancialCalculator._validate_age(current_age, "Current age")
            FinancialCalculator._validate_age(retirement_age, "Retirement age")
            FinancialCalculator._validate_positive(monthly_expense, "Monthly expense")
            FinancialCalculator._validate_percentage(inflation, "Inflation rate")
            FinancialCalculator._validate_percentage(sip_return, "SIP return rate")
            FinancialCalculator._validate_percentage(post_ret_return, "Post-retirement return rate")

            if retirement_age <= current_age:
                raise ValueError("Retirement age must be greater than current age")
            if retirement_age - current_age > 50:
                raise ValueError("Years to retirement cannot exceed 50")
            if post_retirement_years > 50:
                raise ValueError("Post-retirement years cannot exceed 50")

        except ValueError as e:
            logger.error(f"Retirement corpus validation failed: {e}")
            return {"error": str(e)}

        logger.info(f"Calculating retirement corpus: age {current_age}→{retirement_age}, expense ₹{monthly_expense}")

        years_to_retirement = retirement_age - current_age

        # Calculate future monthly expense
        inflation_multiplier = (1 + inflation) ** years_to_retirement
        future_monthly_expense = monthly_expense * inflation_multiplier

        # Annual expense at retirement
        annual_expense_at_retirement = future_monthly_expense * 12

        # Total needed for post-retirement years (simple calculation)
        total_for_post_retirement = annual_expense_at_retirement * post_retirement_years

        # Apply discount factor (money grows post-retirement too)
        discount_factor = (1 + post_ret_return) ** (post_retirement_years / 2)
        corpus_needed = total_for_post_retirement / discount_factor

        # Calculate required monthly SIP
        months_to_retirement = years_to_retirement * 12
        monthly_sip_rate = sip_return / 12

        if monthly_sip_rate == 0:
            monthly_sip_required = corpus_needed / months_to_retirement
        else:
            monthly_sip_required = corpus_needed * monthly_sip_rate / ((((1 + monthly_sip_rate) ** months_to_retirement) - 1) * (1 + monthly_sip_rate))

        total_sip_investment = monthly_sip_required * months_to_retirement

        return {
            "current_age": current_age,
            "retirement_age": retirement_age,
            "years_to_retirement": years_to_retirement,
            "current_monthly_expense": monthly_expense,
            "future_monthly_expense": round(future_monthly_expense, 0),
            "corpus_needed": round(corpus_needed, 0),
            "monthly_sip_required": round(monthly_sip_required, 0),
            "total_sip_investment": round(total_sip_investment, 0),
            "inflation_rate": inflation,
            "assumed_sip_return": sip_return,
            "assumed_post_retirement_return": post_ret_return,
            "post_retirement_years": post_retirement_years,
            "calculation_breakdown": {
                "step1_years_to_retirement": years_to_retirement,
                "step2_inflation_multiplier": round(inflation_multiplier, 2),
                "step3_future_monthly_expense": round(future_monthly_expense, 0),
                "step4_annual_expense_at_retirement": round(annual_expense_at_retirement, 0),
                "step5_total_for_25_years": round(total_for_post_retirement, 0),
                "step6_discount_factor": round(discount_factor, 2),
                "step7_final_corpus": round(corpus_needed, 0)
            }
        }
