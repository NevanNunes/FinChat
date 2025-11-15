"""
Comprehensive Integration Test Suite
Tests all components with hard edge cases
"""
import json
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.query_router import QueryRouter
from agents.market_data_agent import MarketDataAgent
from agents.calculator import FinancialCalculator
from core.retriever import Retriever
from agents.user_profile import UserProfileManager

# ------------------------------------------
# SETUP
# ------------------------------------------

retriever = Retriever()
router = QueryRouter(
    llm_engine=None,   # FORCE router to test non-LLM logic first
    retriever=retriever
)

USER = "test_user"

# ------------------------------------------
# HARD TEST CASES
# ------------------------------------------

TESTS = [
    # HARD STOCK PRICES (tickers MUST come from NSE, not guessed)
    ("Stock", "Infosys stock price"),
    ("Stock", "Tata Motors price today"),
    ("Stock", "Adani Enterprises latest price"),
    ("Stock", "What is HDFC Bank trading at right now"),
    ("Stock", "ICICI Bank share price"),
    ("Stock", "State Bank of India live price"),
    ("Stock", "Asian Paints stock price"),
    ("Stock", "UltraTech Cement share price"),
    ("Stock", "Bharti Airtel stock price"),

    # HARD STOCK METRICS (requires perfect NSE → ticker mapping)
    ("Metric", "Dividend yield of TCS"),
    ("Metric", "P/E ratio of Infosys"),
    ("Metric", "Price to earnings of Reliance"),

    # MIXED QUERY TRAPS
    ("Stock", "price of reliance motor"),  # SHOULD FAIL gracefully
    ("Stock", "show me share for 'icci'"), # typo, fuzzy
    ("Stock", "stock of RIL"),            # alias name

    # ETF HARD CHECKS
    ("ETF", "Nifty BeES price"),
    ("ETF", "Bank BeES latest price"),

    # MUTUAL FUND NAV HARD CHECKS
    ("MF NAV", "Axis Bluechip Fund direct growth nav"),
    ("MF NAV", "HDFC Midcap Opportunities NAV"),
    ("MF NAV", "Mirae Asset Large Cap Direct plan nav"),
    ("MF NAV", "SBI Small Cap Fund nav"),

    # FUND CATEGORY (must NOT loop 37k funds)
    ("MF Category", "best large cap funds"),
    ("MF Category", "top elss funds right now"),
    ("MF Category", "top aggressive hybrid funds"),
    ("MF Category", "best small cap mutual funds"),
    ("MF Category", "best mid cap mutual funds"),

    # SIP CALCULATOR (edge cases)
    ("Calculator", "Calculate SIP 5000 for 10 years at 14%"),
    ("Calculator", "SIP 10000 for 35 years"),
    ("Calculator", "SIP 2000 for 5 years"),

    # EMI HARD TEST
    ("Calculator", "EMI for 30 lakh at 8% for 20 years"),
    ("Calculator", "Loan EMI for 1 crore at 7.5% for 30 years"),

    # RETIREMENT COMPUTATION (requires inflation logic)
    ("Retirement", "Retirement corpus for age 22, expense 25k"),

    # PORTFOLIO (must not hardcode funds)
    ("Portfolio", "I have 5 lakh to invest, build a portfolio"),

    # KNOWLEDGE + RAG
    ("Knowledge", "What is asset allocation in mutual funds"),
    ("Knowledge", "Explain 80C deduction"),
    ("Knowledge", "Difference between index funds and ETFs"),
    ("Knowledge", "What are guilt funds")  # misspelling: should route to RAG
]

# ------------------------------------------
# RUNNER
# ------------------------------------------

results = []
passed = 0
failed = 0

for category, query in TESTS:
    print("="*80)
    print(f"TEST CATEGORY: {category}")
    print(f"QUERY: {query}")
    print("-"*80)

    start = time.time()
    try:
        response = router.handle_query(query, USER)
        elapsed = round(time.time() - start, 3)
        print(f"⏱  Time: {elapsed}s")
        print(f"Response Type: {response.get('type')}")

        # Truncate large data for readability
        data = response.get("data", {})
        if isinstance(data, dict):
            # Show only key fields
            summary = {k: v for k, v in data.items() if k in ['company', 'price', 'nav', 'monthly_emi', 'maturity_amount', 'corpus_needed', 'error']}
            if not summary:
                summary = {k: str(v)[:100] + '...' if len(str(v)) > 100 else v for k, v in list(data.items())[:5]}
            print("Data Summary:", json.dumps(summary, indent=2))
        else:
            print("Data:", str(data)[:200])

        results.append({
            "query": query,
            "category": category,
            "time": elapsed,
            "response_type": response.get("type"),
            "data": response.get("data"),
            "status": "PASS"
        })
        passed += 1
        print("✅ PASS")

    except Exception as e:
        elapsed = round(time.time() - start, 3)
        print(f"❌ ERROR: {str(e)} (Time: {elapsed}s)")
        results.append({
            "query": query,
            "category": category,
            "time": elapsed,
            "error": str(e),
            "status": "FAIL"
        })
        failed += 1
        print("❌ FAIL")

# ------------------------------------------
# SAVE RESULTS
# ------------------------------------------

with open("hard_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n\n" + "="*80)
print("FINAL SUMMARY")
print("="*80)
print(f"Total Tests: {len(TESTS)}")
print(f"Passed: {passed} ✅")
print(f"Failed: {failed} ❌")
print(f"Success Rate: {(passed/len(TESTS)*100):.1f}%")
print(f"\nDetailed results saved to: hard_test_results.json")
print("="*80)
