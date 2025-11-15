"""Query Router - Routes queries to appropriate handlers"""
import logging
from typing import Dict, Any, Optional
import re
from config import *
from core.llm_engine import LLMEngine
from core.retriever import Retriever
from agents.market_data_agent import MarketDataAgent
from agents.calculator import FinancialCalculator
from agents.user_profile import UserProfileManager

logger = logging.getLogger(__name__)

class QueryRouter:
    def __init__(self, llm_engine: LLMEngine = None, retriever: Retriever = None) -> None:
        """Initialize QueryRouter with LLM engine and retriever"""
        self.llm = llm_engine or LLMEngine()
        self.retriever = retriever or Retriever()
        self.market_agent = MarketDataAgent()
        self.calculator = FinancialCalculator()
        self.profile_manager = UserProfileManager()

        # Cache user profiles to prevent multiple loads per session
        self._profile_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("QueryRouter initialized successfully")

    def _get_cached_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile with session caching"""
        if user_id not in self._profile_cache:
            logger.debug(f"Loading profile for user: {user_id}")
            profile_data = self.profile_manager.load_profile(user_id)
            self._profile_cache[user_id] = profile_data if profile_data else {}
        else:
            logger.debug(f"Profile cache hit for user: {user_id}")
        return self._profile_cache[user_id]

    # ===== DETECTION FUNCTIONS (FIXED PRIORITY ORDER) =====

    def _detect_stock_metric(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect P/E ratio, dividend yield queries (HIGHEST PRIORITY)"""
        q = query.lower()

        # Specific metric patterns (MUST come before general stock price)
        metric_patterns = [
            r'\bp/e\s+(?:ratio\s+)?of\b',
            r'\bpe\s+(?:ratio\s+)?of\b',
            r'\bp\s+e\s+(?:ratio\s+)?of\b',
            r'\bdividend\s+yield\s+of\b',
            r'\byield\s+of\b',
            r'\bp/e\s+ratio\b',
            r'\bpe\s+ratio\b',
            r'\bdividend\s+yield\b',
        ]

        if any(re.search(pattern, q) for pattern in metric_patterns):
            # Exclude mutual funds
            if not any(ex in q for ex in ["mutual fund", "fund", "best", "top"]):
                logger.debug(f"✓ Detected stock metric query: {query}")
                return {
                    "action": "get_stock_metric",
                    "parameters": {"query": query}
                }
        return None

    def _detect_stock_price(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect stock price queries"""
        q = query.lower()

        stock_keywords = ["stock", "price", "share", "trading", "quote", "market cap"]

        if any(kw in q for kw in stock_keywords):
            # Exclude mutual funds, calculators, etc.
            exclusions = ["mutual fund", "nav", "sip", "emi", "portfolio",
                         "best", "top", "etf", "bees", "fund", "p/e", "pe ratio", "dividend yield"]
            if not any(ex in q for ex in exclusions):
                logger.debug(f"✓ Detected stock price query: {query}")
                return {
                    "action": "get_stock_price",
                    "parameters": {"query": query}
                }
        return None

    def _detect_etf(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect ETF price queries"""
        q = query.lower()
        if "etf" in q or "bees" in q or "index fund" in q:
            logger.debug(f"✓ Detected ETF query: {query}")
            return {
                "action": "get_etf_price",
                "parameters": {"query": query}
            }
        return None

    def _detect_mf_nav(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect mutual fund NAV queries for specific funds"""
        q = query.lower()
        if "nav" in q or ("mutual fund" in q and "price" in q):
            if not any(cat in q for cat in ["best", "top", "good", "recommend"]):
                logger.debug(f"✓ Detected mutual fund NAV query: {query}")
                return {
                    "action": "search_mutual_fund",
                    "parameters": {"query": query}
                }
        return None

    def _detect_fund_category(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect mutual fund category queries"""
        q = query.lower()

        category_keywords = ["best", "top", "good", "show", "recommend"]
        fund_types = ["large cap", "mid cap", "small cap", "elss", "equity",
                     "debt", "hybrid", "mutual fund", "balanced"]

        if any(cat in q for cat in category_keywords) and any(typ in q for typ in fund_types):
            # Determine category
            category = "equity"
            if "large cap" in q or "largecap" in q:
                category = "large cap"
            elif "mid cap" in q or "midcap" in q:
                category = "mid cap"
            elif "small cap" in q or "smallcap" in q:
                category = "small cap"
            elif "elss" in q or "tax saver" in q:
                category = "elss"
            elif "debt" in q or "bond" in q:
                category = "debt"
            elif "hybrid" in q or "balanced" in q:
                category = "hybrid"

            logger.debug(f"✓ Detected fund category query: {category}")
            return {
                "action": "get_top_funds",
                "parameters": {"category": category, "limit": MF_TOP_FUNDS_LIMIT}
            }
        return None

    def _detect_sip(self, query: str, user_id: str = "guest") -> Optional[Dict[str, Any]]:
        """Detect SIP calculator queries with validation"""
        q = query.lower()

        if "sip" in q:
            # Extract amount - support multiple patterns
            # Pattern 1: "sip of 10k" or "sip 10k" or "10k sip"
            # Pattern 2: "sip of 10000" or "sip 10000" or "10000 sip"
            # Pattern 3: "create/start/invest sip of 10k"

            amount = None

            # Try to find amount with units (k, lakh, crore)
            m_amt = re.search(r'(\d+(?:\.\d+)?)\s*k\b', q)
            if m_amt:
                amount = int(float(m_amt.group(1)) * 1000)
            else:
                # Try to find plain numbers
                m_amt = re.search(r'(\d{3,9})', q)
                if m_amt:
                    amount = int(m_amt.group(1))

            # If no amount found in query, fetch from user profile
            if amount is None:
                logger.debug(f"No amount specified in query, fetching from user profile")
                profile = self._get_cached_profile(user_id).get("profile", {})
                monthly_income = profile.get("monthly_income", 0)

                if isinstance(monthly_income, (int, float)) and monthly_income > 0:
                    # Default SIP: 20% of monthly income
                    amount = int(monthly_income * 0.20)
                    logger.info(f"Using default SIP amount from profile: ₹{amount} (20% of monthly income ₹{monthly_income})")
                else:
                    # Fallback to minimum recommended amount
                    amount = 5000
                    logger.warning(f"No monthly income in profile, using default SIP amount: ₹{amount}")

            # Validate using config
            if not (SIP_MIN_AMOUNT <= amount <= SIP_MAX_AMOUNT):
                logger.warning(f"Invalid SIP amount: ₹{amount}")
                return None

            # Extract years
            m_years = re.search(r'(\d{1,2})\s*(year|years|yrs|y)', q)
            years = int(m_years.group(1)) if m_years else 10

            # Validate years
            if not (SIP_MIN_YEARS <= years <= SIP_MAX_YEARS):
                logger.warning(f"Invalid SIP tenure: {years} years")
                return None

            logger.debug(f"✓ Detected SIP query: amount={amount}, years={years}")
            return {
                "action": "calculate_sip",
                "parameters": {
                    "monthly_sip": amount,
                    "years": years,
                    "expected_return": DEFAULT_SIP_RETURN
                }
            }
        return None

    def _detect_emi(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect EMI calculator queries with validation"""
        q = query.lower()

        if any(kw in q for kw in ["emi", "loan"]):
            # Extract loan amount
            m_amt = re.search(r'(\d+(?:\.\d+)?)\s*(lakh|lakhs|crore|cr|k)?', q)
            if m_amt:
                val = float(m_amt.group(1))
                unit = (m_amt.group(2) or "").lower()

                if "lakh" in unit:
                    amt = int(val * 100000)
                elif "crore" in unit or "cr" in unit:
                    amt = int(val * 10000000)
                elif "k" in unit:
                    amt = int(val * 1000)
                else:
                    amt = int(val)

                # Validate using config
                if not (EMI_MIN_LOAN <= amt <= EMI_MAX_LOAN):
                    logger.warning(f"Invalid loan amount: ₹{amt}")
                    return None

                # Extract interest rate
                m_int = re.search(r'(\d+(?:\.\d+)?)\s*%', q)
                interest = float(m_int.group(1)) if m_int else DEFAULT_EMI_INTEREST

                # Validate interest
                if not (EMI_MIN_INTEREST <= interest <= EMI_MAX_INTEREST):
                    logger.warning(f"Invalid interest rate: {interest}%")
                    return None

                # Extract tenure
                m_tenure = re.search(r'(\d{1,2})\s*(year|years|yrs)', q)
                tenure = int(m_tenure.group(1)) if m_tenure else 20

                # Validate tenure
                if not (EMI_MIN_TENURE <= tenure <= EMI_MAX_TENURE):
                    logger.warning(f"Invalid tenure: {tenure} years")
                    return None

                logger.debug(f"✓ Detected EMI query: amount={amt}, interest={interest}, tenure={tenure}")
                return {
                    "action": "calculate_emi",
                    "parameters": {
                        "loan_amount": amt,
                        "interest_rate": interest,
                        "tenure_years": tenure
                    }
                }
        return None

    def _detect_retirement(self, query: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Detect retirement planning queries with validation"""
        q = query.lower()

        if "retirement" in q or "corpus" in q or "retire" in q:
            profile = self._get_cached_profile(user_id).get("profile", {})

            # Extract current age
            m_age = re.search(r'(?:age|i am|i\'m)\s*(\d{1,2})', q)
            current_age = int(m_age.group(1)) if m_age else profile.get("age", 30)

            # Validate using config
            if not (MIN_AGE <= current_age <= MAX_AGE):
                logger.warning(f"Invalid current age: {current_age}")
                return None

            # Extract retirement age
            m_ret = re.search(r'(?:retire\s*at|retirement\s*age)\s*(\d{2})', q)
            retirement_age = int(m_ret.group(1)) if m_ret else 60

            # Validate
            if not (MIN_RETIREMENT_AGE <= retirement_age <= MAX_RETIREMENT_AGE):
                logger.warning(f"Invalid retirement age: {retirement_age}")
                return None

            if retirement_age <= current_age:
                logger.warning(f"Retirement age must be > current age")
                return None

            # Extract monthly expense
            m_exp = re.search(r'(?:expense|spend|need)\s*(\d+(?:\.\d+)?)\s*(k|lakh|lakhs|crore|cr)?', q)
            if m_exp:
                val = float(m_exp.group(1))
                unit = (m_exp.group(2) or "").lower()
                if "lakh" in unit:
                    monthly_expense = int(val * 100000)
                elif "crore" in unit or "cr" in unit:
                    monthly_expense = int(val * 10000000)
                elif "k" in unit:
                    monthly_expense = int(val * 1000)
                else:
                    monthly_expense = int(val)
            else:
                monthly_income = profile.get("monthly_income", 0)
                if isinstance(monthly_income, (int, float)) and monthly_income > 0:
                    monthly_expense = int(monthly_income * 0.7)
                else:
                    monthly_expense = 50000

            # Validate expense
            if not (MIN_MONTHLY_EXPENSE <= monthly_expense <= MAX_MONTHLY_EXPENSE):
                logger.warning(f"Invalid monthly expense: ₹{monthly_expense}")
                return None

            logger.debug(f"✓ Detected retirement query: age={current_age}, retire={retirement_age}, expense={monthly_expense}")
            return {
                "action": "calculate_retirement",
                "parameters": {
                    "current_age": current_age,
                    "retirement_age": retirement_age,
                    "monthly_expense": monthly_expense
                }
            }
        return None

    def _detect_portfolio(self, query: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Detect portfolio recommendation queries with validation"""
        q = query.lower()

        if "portfolio" in q or ("invest" in q and any(kw in q for kw in ["i have", "create", "suggest", "build"])):
            profile = self._get_cached_profile(user_id).get("profile", {})

            # Extract investment amount
            m_amt = re.search(r'(\d+(?:\.\d+)?)\s*(lakh|lakhs|crore|cr|k)?', q)
            if m_amt:
                val = float(m_amt.group(1))
                unit = (m_amt.group(2) or "").lower()
                if "lakh" in unit:
                    amt = int(val * 100000)
                elif "crore" in unit or "cr" in unit:
                    amt = int(val * 10000000)
                elif "k" in unit:
                    amt = int(val * 1000)
                else:
                    amt = int(val)
            else:
                amt = 100000

            # Validate using config
            if not (MIN_INVESTMENT <= amt <= MAX_INVESTMENT):
                logger.warning(f"Invalid investment amount: ₹{amt}")
                return None

            age = profile.get("age", 30)
            risk = profile.get("risk_appetite", "moderate")

            logger.debug(f"✓ Detected portfolio query: age={age}, risk={risk}, amount={amt}")
            return {
                "action": "get_portfolio_recommendation",
                "parameters": {
                    "age": age,
                    "risk_appetite": risk,
                    "investment_amount": amt
                }
            }
        return None

    def _detect_action_with_priority(self, query: str, user_id: str = "guest") -> Optional[Dict]:
        """
        Detect action with FIXED priority order.

        CRITICAL: Stock metric MUST be detected BEFORE stock price.
        """

        # 1. Stock metric (HIGHEST PRIORITY - P/E, dividend yield)
        result = self._detect_stock_metric(query)
        if result:
            return result

        # 2. Stock price
        result = self._detect_stock_price(query)
        if result:
            return result

        # 3. ETF price
        result = self._detect_etf(query)
        if result:
            return result

        # 4. Mutual fund NAV
        result = self._detect_mf_nav(query)
        if result:
            return result

        # 5. MF category queries
        result = self._detect_fund_category(query)
        if result:
            return result

        # 6. SIP calculator (now passes user_id)
        result = self._detect_sip(query, user_id)
        if result:
            return result

        # 7. EMI calculator
        result = self._detect_emi(query)
        if result:
            return result

        # 8. Retirement corpus
        result = self._detect_retirement(query, user_id)
        if result:
            return result

        # 9. Portfolio recommendation
        result = self._detect_portfolio(query, user_id)
        if result:
            return result

        # No action detected
        return None

    def _execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute detected action with error handling"""
        logger.info(f"Executing action: {action} with params: {parameters}")

        try:
            if action == "get_stock_price":
                return self.market_agent.get_stock_price(parameters["query"])

            elif action == "get_stock_metric":
                return self.market_agent.get_stock_metric(parameters["query"])

            elif action == "get_etf_price":
                return self.market_agent.get_etf_price(parameters["query"])

            elif action == "search_mutual_fund":
                return self.market_agent.search_fund_dynamic(parameters["query"])

            elif action == "get_top_funds":
                return self.market_agent.get_top_funds_by_category(
                    parameters["category"],
                    parameters.get("limit", MF_TOP_FUNDS_LIMIT)
                )

            elif action == "calculate_sip":
                return self.calculator.sip_returns(
                    parameters["monthly_sip"],
                    parameters["years"],
                    parameters.get("expected_return", DEFAULT_SIP_RETURN)
                )

            elif action == "calculate_emi":
                return self.calculator.emi_calculator(
                    parameters["loan_amount"],
                    parameters.get("interest_rate", DEFAULT_EMI_INTEREST),
                    parameters["tenure_years"]
                )

            elif action == "calculate_retirement":
                return self.calculator.retirement_corpus(
                    parameters["current_age"],
                    parameters["retirement_age"],
                    parameters["monthly_expense"]
                )

            elif action == "get_portfolio_recommendation":
                return self.market_agent.get_personalized_portfolio(
                    parameters["age"],
                    parameters["risk_appetite"],
                    parameters["investment_amount"]
                )

            else:
                logger.error(f"Unknown action: {action}")
                return {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Error executing action {action}: {e}", exc_info=True)
            return {"error": f"Error executing {action}: {str(e)}"}

    def _needs_knowledge_retrieval(self, query: str) -> bool:
        """Check if query needs RAG retrieval"""
        knowledge_keywords = [
            "what is", "explain", "difference", "how does", "why",
            "tell me about", "define", "meaning"
        ]
        return any(kw in query.lower() for kw in knowledge_keywords)

    def handle_query(self, query: str, user_id: str = "guest") -> Dict[str, Any]:
        """Main query handler with improved error handling"""
        logger.info(f"[QUERY] User {user_id}: {query}")

        try:
            # Try deterministic detection first (with FIXED priority order)
            detected_action = self._detect_action_with_priority(query, user_id)

            if detected_action:
                # Execute detected action
                result = self._execute_action(detected_action["action"], detected_action["parameters"])

                # Generate summary
                try:
                    summary = self.llm.summarize_data(result, query)
                except Exception as e:
                    logger.warning(f"Summary generation failed: {e}, using fallback")
                    summary = self._fallback_summary(result, query)

                return {
                    "type": "finance_response",
                    "response": summary,
                    "data": result
                }

            # Get user context
            user_context = self.profile_manager.get_context_summary(user_id)

            # Check if query needs RAG
            rag_context = ""
            if self._needs_knowledge_retrieval(query):
                rag_context = self.retriever.get_context(query)

            # Get LLM response
            try:
                llm_response = self.llm.get_response(query, rag_context, user_context)
            except Exception as e:
                logger.error(f"LLM error: {e}")
                return {
                    "type": "error",
                    "response": "I'm having trouble processing your query. The AI service may be unavailable.",
                    "data": {"error": str(e)}
                }

            # Check if LLM returned an action
            if "action" in llm_response and "parameters" in llm_response:
                result = self._execute_action(llm_response["action"], llm_response["parameters"])
                summary = self.llm.summarize_data(result, query)
                return {
                    "type": "finance_response",
                    "response": summary,
                    "data": result
                }

            # Conversational response
            return {
                "type": "conversational",
                "response": llm_response.get("content", "I'm not sure how to help with that."),
                "data": {}
            }

        except Exception as e:
            logger.error(f"Error in handle_query: {e}", exc_info=True)
            return {
                "type": "error",
                "response": f"An error occurred: {str(e)}",
                "data": {"error": str(e)}
            }

    def _fallback_summary(self, data: Dict[str, Any], query: str) -> str:
        """Fallback summary when LLM is unavailable"""
        if "error" in data:
            return f"Sorry, {data['error']}"

        if "company" in data and "price" in data:
            return f"{data['company']} is trading at ₹{data['price']}, {data.get('change_percent', 0):+.2f}% today."

        if "dividend_yield" in data:
            return f"Dividend yield: {data['dividend_yield']}%"

        if "pe_ratio" in data:
            return f"P/E ratio: {data['pe_ratio']}"

        if "monthly_emi" in data:
            return f"Monthly EMI: ₹{data['monthly_emi']:,.0f}"

        if "maturity_amount" in data:
            return f"SIP maturity value: ₹{data['maturity_amount']:,.0f}"

        return "Here's the data you requested."

