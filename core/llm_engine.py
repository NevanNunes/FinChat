"""LLM Engine - Connects to Mistral via LM Studio"""
import json
import os
import logging
import re
from typing import Dict, Any, Optional
from openai import OpenAI
from config import *

logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self, base_url: str = None, api_key: str = None):
        """Initialize LLM Engine with connection to LM Studio"""
        base_url = base_url or os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
        api_key = api_key or os.environ.get("LM_STUDIO_API_KEY", "lm-studio")

        self.client = OpenAI(base_url=base_url, api_key=api_key)

        # Cached prompts (reduces token usage)
        self._system_prompt_cached: Optional[str] = None
        self._action_prompt_cached: Optional[str] = None

        logger.info(f"LLM Engine initialized with base_url: {base_url}")

    def _get_system_prompt(self) -> str:
        """Compact system prompt for conversational mode"""
        if self._system_prompt_cached:
            return self._system_prompt_cached

        self._system_prompt_cached = """You are FinChat, an AI financial advisor for India.

Provide clear, accurate financial information. Consider risk tolerance and time horizon.

Guidelines:
- Be concise (2-4 sentences max)
- Use Indian context (₹, lakhs, crores)
- Cite sources when relevant
- Don't invent numbers
- For tax advice, mention consulting a CA

Topics: stocks, mutual funds, SIP, EMI, retirement, tax saving, portfolio."""

        return self._system_prompt_cached

    def _get_action_prompt(self) -> str:
        """Compact prompt for action detection"""
        if self._action_prompt_cached:
            return self._action_prompt_cached

        self._action_prompt_cached = """Analyze query and output JSON if it maps to an action, otherwise answer directly.

Actions:
- get_stock_price: stock prices
- get_stock_metric: P/E, dividend yield
- get_etf_price: ETF prices
- search_mutual_fund: specific fund NAV
- get_top_funds: best funds by category
- get_portfolio_recommendation: portfolio suggestions
- calculate_sip: SIP calculations
- calculate_emi: loan EMI
- calculate_retirement: retirement corpus

JSON format (single line, no markdown):
{"action":"action_name","parameters":{...}}

Pass exact names. Don't normalize tickers.

For knowledge queries (what is, explain), answer directly without JSON."""

        return self._action_prompt_cached

    def generate(self, prompt: str, json_mode: bool = False, context: str = "", max_tokens: int = 500) -> str:
        """Core generation with optimized token usage"""
        # Build compact message
        if json_mode:
            full_prompt = self._get_action_prompt() + "\n\n"
            if context:
                full_prompt += f"Context: {context[:500]}\n\n"  # Limit context
            full_prompt += f"Query: {prompt}"
            max_tokens = min(max_tokens, LLM_MAX_TOKENS_QUERY)
        else:
            full_prompt = self._get_system_prompt() + "\n\n"
            if context:
                full_prompt += f"Context: {context[:800]}\n\n"  # Limit context
            full_prompt += f"User: {prompt}"
            max_tokens = min(max_tokens, LLM_MAX_TOKENS_CONVERSATION)

        messages = [{"role": "user", "content": full_prompt}]

        try:
            response = self.client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=LLM_TEMPERATURE_JSON if json_mode else LLM_TEMPERATURE_CHAT,
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content.strip()
            logger.debug(f"LLM response: {len(result)} chars (json_mode={json_mode})")
            return result

        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            raise RuntimeError(f"LLM generation failed: {str(e)}")

    def get_response(self, user_query: str, context: str = "", user_profile: str = "") -> Dict[str, Any]:
        """Get response with automatic action detection or conversation"""
        # Combine context (limit size)
        full_context = ""
        if context:
            full_context += context[:600] + "\n"
        if user_profile:
            full_context += user_profile[:200]

        # Try action mode first
        try:
            response = self.generate(user_query, json_mode=True, context=full_context, max_tokens=LLM_MAX_TOKENS_QUERY)

            # Try to extract JSON (handles markdown code blocks)
            parsed = self._extract_json(response)
            if parsed and "action" in parsed and "parameters" in parsed:
                logger.info(f"Action detected: {parsed['action']}")
                return parsed

            # Not valid action JSON, fall back to conversation
            conv_response = self.generate(user_query, json_mode=False, context=full_context, max_tokens=LLM_MAX_TOKENS_CONVERSATION)
            return {"content": conv_response}

        except Exception as e:
            logger.error(f"Error in get_response: {str(e)}")
            return {
                "error": str(e),
                "content": "I'm having trouble connecting to the AI model. Please check if LM Studio is running."
            }

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text with fallback for markdown code blocks"""
        try:
            # Try direct JSON parse
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code blocks
        patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{.*?\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        logger.debug(f"Could not extract JSON from: {text[:100]}")
        return None

    def summarize_data(self, data: Dict[str, Any], original_query: str) -> str:
        """Generate natural language summary with fallback"""
        # Handle errors
        if "error" in data:
            logger.warning(f"Summarizing error response")
            return f"Sorry, I couldn't find information for '{original_query}'. {data.get('error', '')}"

        # Build compact summary prompt
        prompt = f"""Summarize for: "{original_query}"

Data: {json.dumps(data, indent=2)[:1000]}

Requirements:
- Use exact asset name from query
- Include key metrics
- 2-3 sentences max
- Use ₹ for currency
- Don't use ticker symbols

Summary:"""

        try:
            summary = self.generate(prompt, json_mode=False, max_tokens=LLM_MAX_TOKENS_SUMMARY)
            logger.debug(f"Summary generated")
            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}, using fallback")
            return self._fallback_summary(data, original_query)

    def _fallback_summary(self, data: Dict[str, Any], query: str) -> str:
        """Structured summary when LLM is unavailable"""
        # Stock data
        if "company" in data and "price" in data:
            company = data.get("company", query)
            price = data.get("price", "N/A")
            change = data.get("change_percent", 0)
            change_emoji = "📈" if change >= 0 else "📉"
            return f"{company} is currently trading at ₹{price:,.2f}, {change_emoji} {change:+.2f}% today."

        # Dividend yield
        if "dividend_yield" in data:
            company = data.get("company", query)
            dy = data.get("dividend_yield", 0)
            dr = data.get("dividend_rate", 0)
            return f"{company} has a dividend yield of {dy}% with an annual dividend rate of ₹{dr}."

        # P/E ratio
        if "pe_ratio" in data:
            company = data.get("company", query)
            pe = data.get("pe_ratio", "N/A")
            return f"{company} has a P/E ratio of {pe}."

        # SIP
        if "maturity_amount" in data:
            maturity = data.get("maturity_amount", 0)
            invested = data.get("total_invested", 0)
            gains = data.get("gains", 0)
            years = data.get("years", 0)
            monthly_sip = data.get("monthly_sip", 0)
            returns_pct = data.get("returns_percentage", 0)

            summary = f"💰 **SIP Investment Plan**\n\n"
            summary += f"Monthly SIP: ₹{monthly_sip:,.0f}\n"
            summary += f"Investment Period: {years} years\n"
            summary += f"Expected Return: {data.get('expected_return_display', '12.0%')}\n\n"
            summary += f"📊 **Results:**\n"
            summary += f"• Total Invested: ₹{invested:,.0f}\n"
            summary += f"• Maturity Value: ₹{maturity:,.0f}\n"
            summary += f"• Total Gains: ₹{gains:,.0f} ({returns_pct:.1f}%)\n\n"

            # Add milestones if available
            if "milestones" in data:
                milestones = data["milestones"]
                summary += f"📈 **Milestones:**\n"
                for key, value in milestones.items():
                    if value:
                        year_num = value["year"]
                        year_value = value["value"]
                        summary += f"• Year {year_num}: ₹{year_value:,.0f}\n"

            return summary

        # EMI
        if "monthly_emi" in data:
            emi = data.get("monthly_emi", 0)
            loan = data.get("loan_amount", 0)
            total = data.get("total_payment", 0)
            interest = data.get("total_interest", 0)
            tenure = data.get("tenure_years", 0)
            interest_rate = data.get("interest_rate", 0)

            summary = f"🏠 **Loan EMI Calculation**\n\n"
            summary += f"Loan Amount: ₹{loan:,.0f}\n"
            summary += f"Interest Rate: {interest_rate}% per annum\n"
            summary += f"Tenure: {tenure} years\n\n"
            summary += f"📊 **Monthly EMI: ₹{emi:,.0f}**\n\n"
            summary += f"💳 **Total Payment Breakdown:**\n"
            summary += f"• Principal: ₹{loan:,.0f} ({data.get('principal_percentage', 0):.1f}%)\n"
            summary += f"• Interest: ₹{interest:,.0f} ({data.get('interest_percentage', 0):.1f}%)\n"
            summary += f"• Total Payable: ₹{total:,.0f}\n\n"

            # Add first vs last year comparison if available
            if "summary" in data:
                summ = data["summary"]
                summary += f"📈 **Year-wise Breakdown:**\n"
                summary += f"• Year 1: Principal ₹{summ.get('first_year_principal', 0):,.0f}, Interest ₹{summ.get('first_year_interest', 0):,.0f}\n"
                summary += f"• Year {tenure}: Principal ₹{summ.get('last_year_principal', 0):,.0f}, Interest ₹{summ.get('last_year_interest', 0):,.0f}\n"

            return summary

        # Retirement
        if "corpus_needed" in data:
            corpus = data.get("corpus_needed", 0)
            sip = data.get("monthly_sip_required", 0)
            years = data.get("years_to_retirement", 0)
            current_age = data.get("current_age", 0)
            retirement_age = data.get("retirement_age", 0)
            current_exp = data.get("current_monthly_expense", 0)
            future_exp = data.get("future_monthly_expense", 0)

            summary = f"🏖️ **Retirement Planning**\n\n"
            summary += f"Current Age: {current_age} years\n"
            summary += f"Retirement Age: {retirement_age} years\n"
            summary += f"Years to Retirement: {years} years\n\n"
            summary += f"💰 **Expenses:**\n"
            summary += f"• Current Monthly: ₹{current_exp:,.0f}\n"
            summary += f"• At Retirement: ₹{future_exp:,.0f}\n\n"
            summary += f"🎯 **Retirement Corpus Needed: ₹{corpus:,.0f}**\n\n"
            summary += f"📊 **Investment Plan:**\n"
            summary += f"• Monthly SIP Required: ₹{sip:,.0f}\n"
            summary += f"• Total Investment: ₹{data.get('total_sip_investment', 0):,.0f}\n"
            summary += f"• Expected Returns: {data.get('assumed_sip_return', 0.12)*100:.1f}% p.a.\n"

            return summary

        # Mutual fund
        if "nav" in data:
            name = data.get("name", query)
            nav = data.get("nav", 0)
            r1y = data.get("returns_1y", 0)
            return f"{name} has a current NAV of ₹{nav:.2f} with 1-year returns of {r1y:.2f}%."

        # Funds list
        if "funds" in data and isinstance(data["funds"], list) and len(data["funds"]) > 0:
            count = len(data["funds"])
            category = data.get("category", "")
            return f"Here are {count} top {category} mutual funds based on performance and ratings."

        # Portfolio
        if "allocation" in data:
            equity = data.get("profile", {}).get("equity_allocation", 0)
            return f"Based on your profile, I recommend {equity}% equity allocation. Diversify across large cap, mid cap, and debt funds."

        # Default
        return "Here's the information you requested."
