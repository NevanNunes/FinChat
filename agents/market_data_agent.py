"""Market Data Agent - Real-time stock/ETF/dividend/mutual fund data via Yahoo Finance & MFApi"""
import yfinance as yf
import requests
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time
import re
import pickle
from pathlib import Path
from rapidfuzz import fuzz
from config import *

logger = logging.getLogger(__name__)

class MarketDataAgent:
    def __init__(self) -> None:
        """Initialize MarketDataAgent with caching and API configurations"""
        self.cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self.cache_expiry: int = STOCK_CACHE_EXPIRY
        self.headers: Dict[str, str] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json,text/html'
        }
        self.mf_cache_expiry: int = MF_CACHE_EXPIRY

        # Symbol cache (NSE validated symbols only)
        self.symbol_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

        # Negative cache for not-found stocks
        self.negative_cache: Dict[str, float] = {}
        self.negative_cache_expiry: int = NEGATIVE_CACHE_EXPIRY

        # Pre-indexed mutual funds by category
        self.all_funds: List[Dict[str, Any]] = []
        self.funds_by_category: Dict[str, List[Dict[str, Any]]] = {}
        self._load_and_index_funds()

        logger.info("MarketDataAgent initialized successfully")

    def _load_and_index_funds(self) -> None:
        """Load and pre-index all mutual funds by category for fast lookups"""
        logger.info("Loading and indexing mutual funds...")
        try:
            # Try to load from cache
            cache_file = Path("data/mf_cache.pkl")
            if cache_file.exists():
                cache_age = time.time() - cache_file.stat().st_mtime
                if cache_age < 86400:  # 24 hours
                    with open(cache_file, 'rb') as f:
                        cached = pickle.load(f)
                        self.all_funds = cached.get('all_funds', [])
                        self.funds_by_category = cached.get('by_category', {})
                        logger.info(f"Loaded {len(self.all_funds)} funds from cache ({len(self.funds_by_category)} categories)")
                        return

            # Load fresh data from API
            url = "https://api.mfapi.in/mf"
            resp = requests.get(url, timeout=10)

            if resp.status_code == 200:
                self.all_funds = resp.json()
                logger.info(f"Loaded {len(self.all_funds)} funds from API")

                # Index by category
                self._index_funds_by_category()

                # Save to cache
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, 'wb') as f:
                    pickle.dump({
                        'all_funds': self.all_funds,
                        'by_category': self.funds_by_category
                    }, f)
                logger.info(f"Saved fund cache with {len(self.funds_by_category)} categories")
            else:
                logger.warning(f"Failed to load funds from API: {resp.status_code}")
                self.all_funds = []
                self.funds_by_category = {}

        except Exception as e:
            logger.error(f"Error loading mutual funds: {e}")
            self.all_funds = []
            self.funds_by_category = {}

    def _index_funds_by_category(self) -> None:
        """Pre-index funds by category for O(1) category lookups"""
        logger.debug("Indexing funds by category...")

        category_map = {
            'large cap': ['large cap', 'largecap', 'large-cap', 'bluechip', 'blue chip'],
            'mid cap': ['mid cap', 'midcap', 'mid-cap'],
            'small cap': ['small cap', 'smallcap', 'small-cap'],
            'elss': ['elss', 'tax saver', 'tax-saver'],
            'equity': ['equity', 'growth'],
            'debt': ['debt', 'bond', 'income', 'gilt'],
            'hybrid': ['hybrid', 'balanced', 'multi asset'],
        }

        # Initialize category lists
        for cat in category_map:
            self.funds_by_category[cat] = []

        # Index each fund
        for fund in self.all_funds:
            fund_name = fund.get('schemeName', '').lower()

            # Match to categories
            for cat, keywords in category_map.items():
                if any(kw in fund_name for kw in keywords):
                    self.funds_by_category[cat].append(fund)

        logger.info(f"Indexed funds: " + ", ".join([f"{k}={len(v)}" for k, v in self.funds_by_category.items()]))

    def get_stock_price(self, query: str) -> Dict[str, Any]:
        """Fetch real-time stock price with dividend data

        CRITICAL: Uses ONLY NSE-validated tickers. No hardcoding, no guessing.
        """
        logger.info(f"Fetching stock price for: {query}")
        logger.debug(f"[NSE-ONLY MODE] Starting ticker search for: {query}")

        cache_key = f"stock_{query.lower()}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_expiry:
                logger.debug(f"Cache hit for stock: {query}")
                return cached_data

        # Check negative cache
        if cache_key in self.negative_cache:
            timestamp = self.negative_cache[cache_key]
            if time.time() - timestamp < self.negative_cache_expiry:
                logger.info(f"Stock not found (negative cache): {query}")
                return {"error": f"Stock '{query}' not found. Try using the exact company name as listed on NSE."}

        # STEP 1: Search NSE API for ticker
        company_name, symbol = self._search_nse_for_ticker(query)

        # STEP 2: If NSE fails, DO NOT GUESS - return error
        if not symbol:
            logger.warning(f"NSE search failed for: {query}")
            self.negative_cache[cache_key] = time.time()
            return {
                "error": f"Could not find ticker for '{query}' on NSE. Please try the exact company name (e.g., 'Reliance Industries', 'Infosys Limited')."
            }

        # STEP 3: Fetch data from Yahoo Finance using NSE-validated ticker
        try:
            logger.debug(f"Fetching Yahoo Finance data for NSE ticker: {symbol}")
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="1d")

            if hist.empty:
                logger.error(f"No data available for symbol: {symbol}")
                return {"error": f"No data available for {symbol}"}

            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0

            # FIX: Dividend yield - remove double multiplication
            raw_dividend_yield = info.get('dividendYield')
            dividend_yield = round(raw_dividend_yield * 100, 2) if raw_dividend_yield else 0

            result = {
                "company": company_name or info.get('longName', symbol),
                "symbol": symbol,
                "price": round(current_price, 2),
                "change": round(change, 2),
                "change_percent": round(change_pct, 2),
                "volume": int(hist['Volume'].iloc[-1]) if not hist.empty else 0,
                "day_high": round(hist['High'].iloc[-1], 2),
                "day_low": round(hist['Low'].iloc[-1], 2),
                "market_cap": info.get('marketCap', 'N/A'),
                "pe_ratio": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else 'N/A',
                "dividend_yield": dividend_yield,
                "dividend_rate": round(info.get('dividendRate', 0), 2) if info.get('dividendRate') else 0,
                "payout_ratio": round(info.get('payoutRatio', 0) * 100, 2) if info.get('payoutRatio') else 0,
                "data_source": "Yahoo Finance (NSE)"
            }

            self.cache[cache_key] = (result, time.time())
            logger.info(f"Successfully retrieved stock data for {company_name} ({symbol})")
            return result

        except Exception as e:
            logger.error(f"Error fetching stock price for {query}: {str(e)}", exc_info=True)
            return {"error": f"Error fetching data: {str(e)}"}

    def get_stock_metric(self, query: str) -> Dict[str, Any]:
        """Return ONLY the requested metric (PE, Dividend Yield)."""
        logger.info(f"Fetching stock metric for: {query}")

        # Extract stock name from query
        q_lower = query.lower()
        stock_query = query

        # Remove metric keywords to isolate stock name
        stock_query = re.sub(r'\b(dividend\s+yield|yield|dividend\s+rate)\b', '', stock_query, flags=re.IGNORECASE)
        stock_query = re.sub(r'\b(p/e\s+ratio|pe\s+ratio|p\s+e\s+ratio|p/e|pe)\b', '', stock_query, flags=re.IGNORECASE)
        stock_query = re.sub(r'\b(of|for|the)\b', '', stock_query, flags=re.IGNORECASE)
        stock_query = ' '.join(stock_query.split()).strip()

        logger.debug(f"Cleaned stock query: {stock_query}")

        # Get full stock data
        stock = self.get_stock_price(stock_query)

        if not stock or "error" in stock:
            logger.warning(f"Could not fetch stock data for metric query: {query}")
            return stock

        # Return only requested metric
        if "dividend" in q_lower and "yield" in q_lower:
            logger.debug(f"Returning dividend yield metric for {stock['symbol']}")
            return {
                "company": stock["company"],
                "symbol": stock["symbol"],
                "dividend_yield": stock["dividend_yield"],
                "dividend_rate": stock["dividend_rate"],
                "data_source": stock["data_source"]
            }

        if "p/e" in q_lower or "pe ratio" in q_lower or "p e ratio" in q_lower or ("pe" in q_lower and "of" in q_lower):
            logger.debug(f"Returning P/E ratio metric for {stock['symbol']}")
            return {
                "company": stock["company"],
                "symbol": stock["symbol"],
                "pe_ratio": stock["pe_ratio"],
                "data_source": stock["data_source"]
            }

        logger.debug(f"Returning full stock data for {stock['symbol']}")
        return stock

    def _search_nse_for_ticker(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Search NSE API for ticker symbol.

        CRITICAL RULE: Returns (company_name, ticker) ONLY if NSE validates it.
        Returns (None, None) if not found - NO GUESSING ALLOWED.
        """
        logger.debug(f"[NSE-ONLY] Searching NSE for: {query}")

        # Check positive cache
        cache_key = query.lower().strip()
        if cache_key in self.symbol_cache:
            logger.debug(f"Symbol cache hit for: {query}")
            return self.symbol_cache[cache_key]

        # Clean query - remove noise words but preserve company name
        query_clean = query.strip()

        # Remove noise words MORE CAREFULLY
        # Only remove complete phrases, not individual words that might be part of company name
        noise_phrases = [
            r'\bwhat\s+is\s+the\b',
            r'\bwhat\s+is\b',
            r'\bget\s+me\b',
            r'\bshow\s+me\b',
            r'\btell\s+me\b',
            r'\bfind\b',
            r'\bsearch\b',
        ]

        # Remove trailing noise words only (at the end)
        trailing_noise = [
            r'\s+stock\s+price$',
            r'\s+share\s+price$',
            r'\s+price$',
            r'\s+stock$',
            r'\s+share$',
            r'\s+quote$',
            r'\s+trading\s+at$',
            r'\s+today$',
        ]

        query_lower = query_clean.lower()

        # Remove noise phrases
        for pattern in noise_phrases:
            query_lower = re.sub(pattern, '', query_lower, flags=re.IGNORECASE).strip()

        # Remove trailing noise
        for pattern in trailing_noise:
            query_lower = re.sub(pattern, '', query_lower, flags=re.IGNORECASE).strip()

        query_clean = query_lower.strip()

        # If query became empty or too short, use original
        if len(query_clean) < 2:
            query_clean = query.strip().lower()

        logger.debug(f"Cleaned query: '{query_clean}' (from original: '{query}')")

        # Check for common indices
        indices = {
            "nifty 50": ("NIFTY 50", "^NSEI"),
            "nifty": ("NIFTY 50", "^NSEI"),
            "sensex": ("SENSEX", "^BSESN"),
            "bank nifty": ("BANK NIFTY", "^NSEBANK"),
            "nifty bank": ("BANK NIFTY", "^NSEBANK")
        }

        for idx_name, (full_name, idx_ticker) in indices.items():
            if idx_name in query_clean:
                logger.debug(f"Matched index: {idx_name} -> {idx_ticker}")
                result = (full_name, idx_ticker)
                self.symbol_cache[cache_key] = result
                return result

        # Try NSE autocomplete with cleaned query
        logger.debug(f"Calling NSE API with query: '{query_clean}'")
        company_name, ticker, error = self._call_nse_autocomplete(query_clean)

        if ticker:
            # Success - cache and return
            result = (company_name, ticker)
            self.symbol_cache[cache_key] = result
            logger.info(f"[NSE-ONLY] Found ticker: {ticker} for '{query}'")
            return result

        # If cleaned query failed, try with first word(s) as company name
        # E.g., "Infosys Limited" → try "Infosys" if full name fails
        if len(query_clean.split()) > 1:
            first_word = query_clean.split()[0]
            logger.debug(f"Trying first word fallback: '{first_word}'")
            company_name, ticker, error = self._call_nse_autocomplete(first_word)

            if ticker:
                result = (company_name, ticker)
                self.symbol_cache[cache_key] = result
                logger.info(f"[NSE-ONLY] Found ticker: {ticker} using first word '{first_word}'")
                return result

        # NSE failed - DO NOT GUESS
        logger.warning(f"[NSE-ONLY] NSE search failed for '{query}': {error}")
        return None, None

    def _call_nse_autocomplete(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Call NSE autocomplete API with retries and proper error handling.
        Returns (company_name, ticker_with_NS_suffix, error_reason)
        """
        logger.debug(f"Calling NSE autocomplete API for: {query}")

        for attempt in range(NSE_MAX_RETRIES + 1):
            try:
                url = f"https://www.nseindia.com/api/search/autocomplete?q={requests.utils.quote(query)}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }

                resp = requests.get(url, headers=headers, timeout=NSE_TIMEOUT)

                # Handle rate limiting
                if resp.status_code == 429:
                    if attempt < NSE_MAX_RETRIES:
                        delay = NSE_BASE_DELAY * (2 ** attempt)
                        logger.warning(f"NSE rate limited, retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    return None, None, "rate_limited"

                # Handle server errors
                if resp.status_code >= 500:
                    if attempt < NSE_MAX_RETRIES:
                        delay = NSE_BASE_DELAY * (2 ** attempt)
                        logger.warning(f"NSE server error, retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    return None, None, f"server_error_{resp.status_code}"

                # Handle other HTTP errors
                if resp.status_code != 200:
                    logger.warning(f"NSE API returned status {resp.status_code}")
                    return None, None, f"http_error_{resp.status_code}"

                # Parse response
                try:
                    data = resp.json()
                except ValueError:
                    return None, None, "invalid_json"

                # Extract symbols
                if "symbols" not in data or not data["symbols"]:
                    logger.debug(f"No symbols found for: {query}")
                    return None, None, "no_symbols"

                # Get best match
                best = data["symbols"][0]
                symbol = best.get("symbol")

                if not symbol:
                    return None, None, "missing_symbol"

                company_name = best.get("symbol_info", symbol)
                ticker = symbol + ".NS"

                logger.debug(f"NSE found: {company_name} ({ticker})")
                return company_name, ticker, None

            except requests.Timeout:
                if attempt < NSE_MAX_RETRIES:
                    delay = NSE_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"NSE timeout, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                return None, None, "timeout"

            except requests.RequestException as e:
                logger.error(f"NSE request error: {e}")
                return None, None, f"request_error"

            except Exception as e:
                logger.error(f"Unexpected NSE error: {e}", exc_info=True)
                return None, None, "unexpected_error"

        return None, None, "max_retries_exceeded"

    def get_etf_price(self, query: str) -> Dict[str, Any]:
        """Fetch ETF price

        Args:
            query: ETF name or symbol to search for

        Returns:
            Dictionary containing ETF price data or error message
        """
        logger.info(f"Fetching ETF price for: {query}")
        company, ticker = self._search_ticker(query)
        if not ticker:
            logger.warning(f"ETF not found: {query}")
            return {"error": f"ETF '{query}' not found"}

        try:
            logger.debug(f"Fetching ETF data for ticker: {ticker}")
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            info = stock.info

            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev_close = info.get('previousClose', price)
                change = price - prev_close
                change_pct = (change / prev_close) * 100 if prev_close else 0

                result = {
                    "etf_name": company or info.get('longName', query),
                    "ticker": ticker,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "volume": int(hist['Volume'].iloc[-1]),
                    "data_source": "Yahoo Finance"
                }
                logger.info(f"Successfully retrieved ETF data for {ticker}")
                return result

            logger.warning(f"No data available for ETF: {query}")
            return {"error": f"No data for '{query}'"}
        except Exception as e:
            logger.error(f"Error fetching ETF price for {query}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def get_nifty_stocks_list(self) -> List[str]:
        """Get list of Nifty 50 stocks for LLM to query

        Returns:
            List of Nifty 50 stock symbols
        """
        logger.info("Fetching Nifty 50 stocks list")
        stocks = self._fetch_nifty_stocks()
        logger.info(f"Retrieved {len(stocks)} Nifty stocks")
        return stocks

    def _search_nse_company(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Search NSE India autocomplete API to get the official company symbol.
        Returns (company_name, ticker_symbol, error_reason).

        Args:
            query: Company name to search for

        Returns:
            Tuple of (company_name, ticker_symbol, error_reason) or (None, None, error_msg) if not found
        """
        logger.debug(f"Searching NSE for company: {query}")

        max_retries = 2
        base_delay = 0.5

        for attempt in range(max_retries + 1):
            try:
                url = "https://www.nseindia.com/api/search/autocomplete?q=" + query
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                }

                # Make request with timeout
                resp = requests.get(url, headers=headers, timeout=5)

                # Check HTTP status
                if resp.status_code == 429:
                    # Rate limited
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"NSE API rate limited for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"NSE API rate limited for '{query}' after {max_retries + 1} attempts")
                        return None, None, "rate_limited"

                elif resp.status_code == 404:
                    logger.debug(f"NSE API returned 404 for query: {query}")
                    return None, None, "not_found"

                elif resp.status_code >= 500:
                    # Server error
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"NSE API server error ({resp.status_code}) for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"NSE API server error ({resp.status_code}) for '{query}' after {max_retries + 1} attempts")
                        return None, None, f"server_error_{resp.status_code}"

                elif resp.status_code != 200:
                    logger.warning(f"NSE API returned status {resp.status_code} for query: {query}")
                    return None, None, f"http_error_{resp.status_code}"

                # Parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    logger.error(f"NSE API returned invalid JSON for '{query}': {str(e)}")
                    return None, None, "invalid_json"

                # Check for symbols in response
                if "symbols" not in data or not data["symbols"]:
                    logger.debug(f"No symbols found in NSE API response for: {query}")
                    return None, None, "no_symbols"

                # Extract best match
                best = data["symbols"][0]
                name = best.get("symbol_info", best.get("symbol", query))
                symbol = best.get("symbol")

                if not symbol:
                    logger.warning(f"NSE API returned symbol data without symbol field for: {query}")
                    return None, None, "missing_symbol_field"

                logger.debug(f"NSE search found: {name} ({symbol})")
                # return NSE-format symbol with no error
                return name, symbol + ".NS", None

            except requests.Timeout as e:
                # Timeout error - retry
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"NSE API timeout for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"NSE API timeout for '{query}' after {max_retries + 1} attempts: {str(e)}")
                    return None, None, "timeout"

            except requests.ConnectionError as e:
                # Network/connection error - retry
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"NSE API connection error for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"NSE API connection error for '{query}' after {max_retries + 1} attempts: {str(e)}")
                    return None, None, "connection_error"

            except requests.RequestException as e:
                # Other request errors
                logger.error(f"NSE API request error for '{query}': {str(e)}")
                return None, None, f"request_error: {type(e).__name__}"

            except Exception as e:
                # Unexpected errors
                logger.error(f"Unexpected error in NSE API search for '{query}': {str(e)}", exc_info=True)
                return None, None, f"unexpected_error: {type(e).__name__}"

        # Should not reach here, but just in case
        return None, None, "max_retries_exceeded"

    def _search_ticker(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Search for ticker symbol with caching, negative caching, and timeout limits

        Args:
            query: Company name or symbol to search for

        Returns:
            Tuple of (company_name, ticker_symbol) or (None, None) if not found
        """
        logger.debug(f"Searching for ticker: {query}")

        # Check positive cache first
        cache_key = query.lower().strip()
        if cache_key in self.symbol_cache:
            logger.debug(f"Symbol cache hit for: {query}")
            return self.symbol_cache[cache_key]

        # Check negative cache (stocks not found)
        if cache_key in self.negative_cache:
            timestamp = self.negative_cache[cache_key]
            if time.time() - timestamp < self.negative_cache_expiry:
                logger.debug(f"Negative cache hit for: {query} (not found within last hour)")
                return None, None

        # Clean the query - remove common noise words
        query_clean = query.strip()

        # Remove common question/command words and phrases
        noise_patterns = [
            r'\bwhat\s+is\b', r'\bprice\s+of\b', r'\btrading\s+at\b',
            r'\btoday\b', r'\bshare\b', r'\bstock\b', r'\bquote\b', r'\betf\b',
            r'\bp/e\s+ratio\s+of\b', r'\bdividend\s+yield\s+of\b',
            r'\bratio\s+of\b', r'\byield\s+of\b',
        ]

        query_lower = query_clean.lower()
        for pattern in noise_patterns:
            query_lower = re.sub(pattern, '', query_lower, flags=re.IGNORECASE)

        query_clean = query_lower.strip()
        logger.debug(f"Cleaned query: {query_clean}")

        # Check for common indices first
        indices = {
            "nifty 50": "^NSEI", "nifty": "^NSEI", "sensex": "^BSESN",
            "bank nifty": "^NSEBANK", "nifty bank": "^NSEBANK"
        }

        for idx_name, idx_ticker in indices.items():
            if idx_name in query_clean:
                logger.debug(f"Matched index: {idx_name} -> {idx_ticker}")
                result = (idx_name.upper(), idx_ticker)
                self.symbol_cache[cache_key] = result
                return result

        # Call NSE autocomplete API
        company_name, ticker, error = self._call_nse_autocomplete(query_clean)

        if ticker:
            # Success - cache and return
            result = (company_name, ticker)
            self.symbol_cache[cache_key] = result
            logger.info(f"Found ticker: {ticker} for {query}")
            return result

        # NSE failed - DO NOT GUESS
        logger.warning(f"NSE search failed for '{query}': {error}")
        return None, None

    def get_multiple_stocks(self, stock_list: List[str]) -> Dict[str, Any]:
        """Fetch data for multiple stocks - useful for top dividend queries

        Args:
            stock_list: List of stock names or symbols

        Returns:
            Dictionary containing data for all successfully fetched stocks
        """
        logger.info(f"Fetching data for {len(stock_list)} stocks")
        results: List[Dict[str, Any]] = []

        for stock_query in stock_list:
            # Clean stock symbol if it already has .NS or .BO suffix
            if not any(stock_query.endswith(suffix) for suffix in ['.NS', '.BO', '.BSE', '.NSE']):
                stock_data = self.get_stock_price(stock_query)
            else:
                # If already has suffix, use direct ticker lookup
                logger.debug(f"Using direct ticker lookup for {stock_query}")
                try:
                    ticker = yf.Ticker(stock_query)
                    hist = ticker.history(period="1d")
                    info = ticker.info

                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = info.get('previousClose', current_price)
                        change = current_price - prev_close
                        change_pct = (change / prev_close) * 100 if prev_close else 0

                        stock_data = {
                            "company": info.get('longName', stock_query),
                            "symbol": stock_query,
                            "price": round(current_price, 2),
                            "change": round(change, 2),
                            "change_percent": round(change_pct, 2),
                            "volume": int(hist['Volume'].iloc[-1]) if not hist.empty else 0,
                            "day_high": round(hist['High'].iloc[-1], 2),
                            "day_low": round(hist['Low'].iloc[-1], 2),
                            "market_cap": info.get('marketCap', 'N/A'),
                            "pe_ratio": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else 'N/A',
                            "dividend_yield": round(info.get('dividendYield', 0), 2) if info.get('dividendYield') else 0,
                            "dividend_rate": round(info.get('dividendRate', 0), 2) if info.get('dividendRate') else 0,
                            "payout_ratio": round(info.get('payoutRatio', 0) * 100, 2) if info.get('payoutRatio') else 0,
                            "data_source": "Yahoo Finance"
                        }
                        logger.debug(f"Successfully fetched {stock_query}")
                    else:
                        logger.warning(f"No data available for {stock_query}")
                        continue
                except Exception as e:
                    logger.error(f"Error fetching {stock_query}: {str(e)}")
                    continue

            if "error" not in stock_data:
                results.append(stock_data)

        logger.info(f"Successfully fetched {len(results)} out of {len(stock_list)} stocks")
        return {
            "success": True,
            "stocks": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat(),
            "data_source": "Yahoo Finance"
        }

    def get_etf_price(self, query: str) -> Dict[str, Any]:
        """Fetch ETF price

        Args:
            query: ETF name or symbol to search for

        Returns:
            Dictionary containing ETF price data or error message
        """
        logger.info(f"Fetching ETF price for: {query}")
        company, ticker = self._search_ticker(query)
        if not ticker:
            logger.warning(f"ETF not found: {query}")
            return {"error": f"ETF '{query}' not found"}

        try:
            logger.debug(f"Fetching ETF data for ticker: {ticker}")
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            info = stock.info

            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev_close = info.get('previousClose', price)
                change = price - prev_close
                change_pct = (change / prev_close) * 100 if prev_close else 0

                result = {
                    "etf_name": company or info.get('longName', query),
                    "ticker": ticker,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "volume": int(hist['Volume'].iloc[-1]),
                    "data_source": "Yahoo Finance"
                }
                logger.info(f"Successfully retrieved ETF data for {ticker}")
                return result

            logger.warning(f"No data available for ETF: {query}")
            return {"error": f"No data for '{query}'"}
        except Exception as e:
            logger.error(f"Error fetching ETF price for {query}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def get_nifty_stocks_list(self) -> List[str]:
        """Get list of Nifty 50 stocks for LLM to query

        Returns:
            List of Nifty 50 stock symbols
        """
        logger.info("Fetching Nifty 50 stocks list")
        stocks = self._fetch_nifty_stocks()
        logger.info(f"Retrieved {len(stocks)} Nifty stocks")
        return stocks

    def _search_nse_company(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Search NSE India autocomplete API to get the official company symbol.
        Returns (company_name, ticker_symbol, error_reason).

        Args:
            query: Company name to search for

        Returns:
            Tuple of (company_name, ticker_symbol, error_reason) or (None, None, error_msg) if not found
        """
        logger.debug(f"Searching NSE for company: {query}")

        max_retries = 2
        base_delay = 0.5

        for attempt in range(max_retries + 1):
            try:
                url = "https://www.nseindia.com/api/search/autocomplete?q=" + query
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                }

                # Make request with timeout
                resp = requests.get(url, headers=headers, timeout=5)

                # Check HTTP status
                if resp.status_code == 429:
                    # Rate limited
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"NSE API rate limited for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"NSE API rate limited for '{query}' after {max_retries + 1} attempts")
                        return None, None, "rate_limited"

                elif resp.status_code == 404:
                    logger.debug(f"NSE API returned 404 for query: {query}")
                    return None, None, "not_found"

                elif resp.status_code >= 500:
                    # Server error
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"NSE API server error ({resp.status_code}) for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"NSE API server error ({resp.status_code}) for '{query}' after {max_retries + 1} attempts")
                        return None, None, f"server_error_{resp.status_code}"

                elif resp.status_code != 200:
                    logger.warning(f"NSE API returned status {resp.status_code} for query: {query}")
                    return None, None, f"http_error_{resp.status_code}"

                # Parse JSON response
                try:
                    data = resp.json()
                except ValueError as e:
                    logger.error(f"NSE API returned invalid JSON for '{query}': {str(e)}")
                    return None, None, "invalid_json"

                # Check for symbols in response
                if "symbols" not in data or not data["symbols"]:
                    logger.debug(f"No symbols found in NSE API response for: {query}")
                    return None, None, "no_symbols"

                # Extract best match
                best = data["symbols"][0]
                name = best.get("symbol_info", best.get("symbol", query))
                symbol = best.get("symbol")

                if not symbol:
                    logger.warning(f"NSE API returned symbol data without symbol field for: {query}")
                    return None, None, "missing_symbol_field"

                logger.debug(f"NSE search found: {name} ({symbol})")
                # return NSE-format symbol with no error
                return name, symbol + ".NS", None

            except requests.Timeout as e:
                # Timeout error - retry
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"NSE API timeout for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"NSE API timeout for '{query}' after {max_retries + 1} attempts: {str(e)}")
                    return None, None, "timeout"

            except requests.ConnectionError as e:
                # Network/connection error - retry
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"NSE API connection error for '{query}', retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"NSE API connection error for '{query}' after {max_retries + 1} attempts: {str(e)}")
                    return None, None, "connection_error"

            except requests.RequestException as e:
                # Other request errors
                logger.error(f"NSE API request error for '{query}': {str(e)}")
                return None, None, f"request_error: {type(e).__name__}"

            except Exception as e:
                # Unexpected errors
                logger.error(f"Unexpected error in NSE API search for '{query}': {str(e)}", exc_info=True)
                return None, None, f"unexpected_error: {type(e).__name__}"

        # Should not reach here, but just in case
        return None, None, "max_retries_exceeded"

    def _search_ticker(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Search for ticker symbol with caching, negative caching, and timeout limits

        Args:
            query: Company name or symbol to search for

        Returns:
            Tuple of (company_name, ticker_symbol) or (None, None) if not found
        """
        logger.debug(f"Searching for ticker: {query}")

        # Check positive cache first
        cache_key = query.lower().strip()
        if cache_key in self.symbol_cache:
            logger.debug(f"Symbol cache hit for: {query}")
            return self.symbol_cache[cache_key]

        # Check negative cache (stocks not found)
        if cache_key in self.negative_cache:
            timestamp = self.negative_cache[cache_key]
            if time.time() - timestamp < self.negative_cache_expiry:
                logger.debug(f"Negative cache hit for: {query} (not found within last hour)")
                return None, None

        # Clean the query - remove common noise words
        query_clean = query.strip()

        # Remove common question/command words and phrases
        noise_patterns = [
            r'\bwhat\s+is\b', r'\bprice\s+of\b', r'\btrading\s+at\b',
            r'\btoday\b', r'\bshare\b', r'\bstock\b', r'\bquote\b', r'\betf\b',
            r'\bp/e\s+ratio\s+of\b', r'\bdividend\s+yield\s+of\b',
            r'\bratio\s+of\b', r'\byield\s+of\b',
        ]

        query_lower = query_clean.lower()
        for pattern in noise_patterns:
            query_lower = re.sub(pattern, '', query_lower, flags=re.IGNORECASE)

        query_clean = query_lower.strip()
        logger.debug(f"Cleaned query: {query_clean}")

        # Check for common indices first
        indices = {
            "nifty 50": "^NSEI", "nifty": "^NSEI", "sensex": "^BSESN",
            "bank nifty": "^NSEBANK", "nifty bank": "^NSEBANK"
        }

        for idx_name, idx_ticker in indices.items():
            if idx_name in query_clean:
                logger.debug(f"Matched index: {idx_name} -> {idx_ticker}")
                result = (idx_name.upper(), idx_ticker)
                self.symbol_cache[cache_key] = result
                return result

        # Call NSE autocomplete API
        company_name, ticker, error = self._call_nse_autocomplete(query_clean)

        if ticker:
            # Success - cache and return
            result = (company_name, ticker)
            self.symbol_cache[cache_key] = result
            logger.info(f"Found ticker: {ticker} for {query}")
            return result

        # NSE failed - DO NOT GUESS
        logger.warning(f"NSE search failed for '{query}': {error}")
        return None, None

    def get_multiple_stocks(self, stock_list: List[str]) -> Dict[str, Any]:
        """Fetch data for multiple stocks - useful for top dividend queries

        Args:
            stock_list: List of stock names or symbols

        Returns:
            Dictionary containing data for all successfully fetched stocks
        """
        logger.info(f"Fetching data for {len(stock_list)} stocks")
        results: List[Dict[str, Any]] = []

        for stock_query in stock_list:
            # Clean stock symbol if it already has .NS or .BO suffix
            if not any(stock_query.endswith(suffix) for suffix in ['.NS', '.BO', '.BSE', '.NSE']):
                stock_data = self.get_stock_price(stock_query)
            else:
                # If already has suffix, use direct ticker lookup
                logger.debug(f"Using direct ticker lookup for {stock_query}")
                try:
                    ticker = yf.Ticker(stock_query)
                    hist = ticker.history(period="1d")
                    info = ticker.info

                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = info.get('previousClose', current_price)
                        change = current_price - prev_close
                        change_pct = (change / prev_close) * 100 if prev_close else 0

                        stock_data = {
                            "company": info.get('longName', stock_query),
                            "symbol": stock_query,
                            "price": round(current_price, 2),
                            "change": round(change, 2),
                            "change_percent": round(change_pct, 2),
                            "volume": int(hist['Volume'].iloc[-1]) if not hist.empty else 0,
                            "day_high": round(hist['High'].iloc[-1], 2),
                            "day_low": round(hist['Low'].iloc[-1], 2),
                            "market_cap": info.get('marketCap', 'N/A'),
                            "pe_ratio": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else 'N/A',
                            "dividend_yield": round(info.get('dividendYield', 0), 2) if info.get('dividendYield') else 0,
                            "dividend_rate": round(info.get('dividendRate', 0), 2) if info.get('dividendRate') else 0,
                            "payout_ratio": round(info.get('payoutRatio', 0) * 100, 2) if info.get('payoutRatio') else 0,
                            "data_source": "Yahoo Finance"
                        }
                        logger.debug(f"Successfully fetched {stock_query}")
                    else:
                        logger.warning(f"No data available for {stock_query}")
                        continue
                except Exception as e:
                    logger.error(f"Error fetching {stock_query}: {str(e)}")
                    continue

            if "error" not in stock_data:
                results.append(stock_data)

        logger.info(f"Successfully fetched {len(results)} out of {len(stock_list)} stocks")
        return {
            "success": True,
            "stocks": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat(),
            "data_source": "Yahoo Finance"
        }

    # ===== MUTUAL FUND METHODS =====

    def search_fund_dynamic(self, query: str) -> Dict[str, Any]:
        """Search for mutual fund by name with optimized category-aware matching

        Args:
            query: Mutual fund name to search for

        Returns:
            Dictionary containing fund details or error message with candidates
        """
        logger.info(f"Searching for mutual fund: {query}")
        cache_key = f"fund_{query.lower()}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.mf_cache_expiry:
                logger.debug(f"Cache hit for fund: {query}")
                return cached_data

        try:
            query_clean = query.lower().replace("nav", "").replace("mutual fund", "").replace("fund", "").strip()
            logger.debug(f"Cleaned fund query: {query_clean}")

            # Category keywords for intelligent matching
            category_keywords = {
                "large cap": ["large", "largecap", "large-cap", "bluechip", "blue chip"],
                "mid cap": ["mid", "midcap", "mid-cap", "mid cap"],
                "small cap": ["small", "smallcap", "small-cap", "small cap"],
                "elss": ["elss", "tax saver", "tax-saver", "taxsaver", "tax"],
                "equity": ["equity"],
                "hybrid": ["hybrid", "balanced"],
                "debt": ["debt", "bond", "liquid"],
            }

            # Detect category filter
            detected_category = None
            for category, keywords in category_keywords.items():
                if any(kw in query_clean for kw in keywords):
                    detected_category = category
                    logger.debug(f"Detected fund category: {category}")
                    break

            # OPTIMIZATION: If category detected, filter first to reduce search space
            search_pool = self.all_funds
            if detected_category:
                # Pre-filter by category keywords
                category_kws = category_keywords[detected_category]
                search_pool = [
                    f for f in self.all_funds
                    if any(kw in f.get("schemeName", "").lower() for kw in category_kws)
                ]
                logger.debug(f"Filtered to {len(search_pool)} funds in {detected_category} category")

            # OPTIMIZATION: Limit fuzzy matching to top candidates only (not all 37k)
            best_match = None
            best_score = 0
            max_candidates = 20 if detected_category else 100  # Reduced search space

            candidates: List[Tuple[Dict[str, Any], int]] = []
            for fund in search_pool[:max_candidates] if not detected_category else search_pool:
                fund_name = fund.get("schemeName", "").lower()

                # Calculate similarity score
                score = fuzz.token_set_ratio(query_clean, fund_name)

                # Boost for exact substring match
                if query_clean in fund_name:
                    score += 10

                candidates.append((fund, score))

                # Track best match
                if score > best_score and score >= 55:
                    best_score = score
                    best_match = fund

            # If we have a good match, return it
            if best_match:
                scheme_code = best_match.get("schemeCode")
                logger.info(f"Found best match with score {best_score}: {best_match.get('schemeName')}")
                fund_details = self._get_fund_details(scheme_code)
                if fund_details:
                    self.cache[cache_key] = (fund_details, time.time())
                    return fund_details

            # Return top 3 candidates sorted by score
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = [
                {
                    "schemeName": fund.get("schemeName"),
                    "schemeCode": fund.get("schemeCode"),
                    "score": score
                }
                for fund, score in candidates[:3]
            ]

            logger.warning(f"No exact match found for '{query}', returning {len(top_candidates)} candidates")
            return {"error": f"No exact fund match for '{query}'", "candidates": top_candidates}

        except Exception as e:
            logger.error(f"Fund search error for '{query}': {str(e)}", exc_info=True)
            return {"error": f"Fund search error: {str(e)}"}

    def get_top_funds_by_category(self, category: str = "equity", limit: int = 5) -> Dict[str, Any]:
        """Get top funds by category

        Args:
            category: Fund category (e.g., 'equity', 'large cap', 'elss')
            limit: Maximum number of funds to return

        Returns:
            Dictionary containing list of top funds or error message
        """
        logger.info(f"Fetching top {limit} funds in category: {category}")
        try:
            category_lower = category.lower().replace("_", " ")

            category_keywords = {
                "large cap": ["large", "largecap", "large-cap"],
                "mid cap": ["mid", "midcap", "mid-cap"],
                "small cap": ["small", "smallcap", "small-cap"],
                "equity": ["equity"],
                "elss": ["elss", "tax saver", "tax-saver", "taxsaver"]
            }

            # Get relevant keywords for the category
            keywords = category_keywords.get(category_lower, [category_lower])
            logger.debug(f"Using keywords for search: {keywords}")

            # First pass: collect direct plans
            filtered_funds: List[Dict[str, Any]] = []
            for fund in self.all_funds:
                scheme_name_lower = fund.get("schemeName", "").lower()
                is_direct = any(token in scheme_name_lower for token in ["direct", "direct plan", "direct-plan", "directplan"])

                if any(kw in scheme_name_lower for kw in keywords) and is_direct:
                    scheme_code = fund.get("schemeCode")
                    details = self._get_fund_details(scheme_code)
                    if details:
                        details["plan_type"] = "direct"
                        filtered_funds.append(details)
                        if len(filtered_funds) >= limit:
                            break

            # Second pass: if no direct plans found, collect regular plans
            if not filtered_funds:
                logger.debug("No direct plans found, searching for regular plans")
                for fund in self.all_funds:
                    scheme_name_lower = fund.get("schemeName", "").lower()

                    if any(kw in scheme_name_lower for kw in keywords):
                        scheme_code = fund.get("schemeCode")
                        details = self._get_fund_details(scheme_code)
                        if details:
                            details["plan_type"] = "regular"
                            filtered_funds.append(details)
                            if len(filtered_funds) >= limit:
                                break

            if not filtered_funds:
                logger.warning(f"No funds found for category '{category}'")
                return {"error": f"No funds found for '{category}'"}

            logger.info(f"Successfully found {len(filtered_funds)} funds in category '{category}'")
            return {
                "success": True,
                "category": category.replace("_", " ").title(),
                "funds": filtered_funds,
                "data_source": "MFApi"
            }
        except Exception as e:
            logger.error(f"Error fetching top funds for category '{category}': {str(e)}", exc_info=True)
            return {"error": str(e)}

    def get_personalized_portfolio(self, age: int, risk_appetite: str, investment_amount: float) -> Dict[str, Any]:
        """Generate personalized portfolio recommendation

        Args:
            age: Investor's age
            risk_appetite: Risk appetite ('aggressive', 'moderate', or 'conservative')
            investment_amount: Monthly investment amount

        Returns:
            Dictionary containing personalized portfolio allocation and recommendations
        """
        logger.info(f"Generating personalized portfolio for age={age}, risk={risk_appetite}, amount={investment_amount}")
        try:
            equity_pct = self._calculate_equity_allocation(age, risk_appetite)
            debt_pct = 100 - equity_pct
            logger.debug(f"Calculated allocation: {equity_pct}% equity, {debt_pct}% debt")

            allocation: Dict[str, float] = {}
            if equity_pct >= 70:
                allocation = {"large cap": 0.40, "mid cap": 0.30, "small cap": 0.20, "elss": 0.10}
            elif equity_pct >= 50:
                allocation = {"large cap": 0.50, "mid cap": 0.30, "hybrid": 0.20}
            else:
                allocation = {"large cap": 0.30, "hybrid": 0.40, "debt": 0.30}

            portfolio: Dict[str, Any] = {
                "total_investment": investment_amount,
                "allocation": allocation,
                "recommended_funds": {},
                "profile": {
                    "age": age,
                    "risk_appetite": risk_appetite,
                    "equity_allocation": equity_pct,
                    "debt_allocation": debt_pct
                }
            }

            for category, percentage in allocation.items():
                logger.debug(f"Fetching top funds for {category} ({percentage*100}%)")
                funds_data = self.get_top_funds_by_category(category, limit=3)
                if funds_data.get("success"):
                    portfolio["recommended_funds"][category] = {
                        "allocation_percentage": percentage * 100,
                        "monthly_amount": round(investment_amount * percentage, 0),
                        "top_funds": funds_data["funds"]
                    }

            logger.info(f"Successfully generated personalized portfolio with {len(portfolio['recommended_funds'])} categories")
            return portfolio
        except Exception as e:
            logger.error(f"Error generating personalized portfolio: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _get_fund_details(self, scheme_code: str) -> Optional[Dict[str, Any]]:
        """Get detailed fund information

        Args:
            scheme_code: Mutual fund scheme code

        Returns:
            Dictionary containing fund details or None if not found
        """
        logger.debug(f"Fetching fund details for scheme code: {scheme_code}")
        try:
            response = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=5)
            if response.status_code != 200:
                logger.warning(f"MFApi returned status {response.status_code} for scheme {scheme_code}")
                return None

            data = response.json()
            nav_data = data.get("data", [])

            if not nav_data or len(nav_data) < 2:
                logger.warning(f"Insufficient NAV data for scheme {scheme_code}")
                return None

            current_nav = float(nav_data[0].get("nav", 0))
            returns_1y = self._calculate_returns(nav_data, 252)
            returns_3y = self._calculate_returns(nav_data, 756)

            fund_name = data.get("meta", {}).get("scheme_name", "Unknown")
            logger.debug(f"Successfully fetched details for {fund_name}")

            return {
                "name": fund_name,
                "nav": current_nav,
                "fund_house": data.get("meta", {}).get("fund_house", "Unknown"),
                "returns_1y": returns_1y,
                "returns_3y": returns_3y,
                "data_source": "MFApi"
            }
        except Exception as e:
            logger.error(f"Error fetching fund details for scheme {scheme_code}: {str(e)}")
            return None

    def _calculate_returns(self, nav_data: List[Dict[str, Any]], days_back: int) -> float:
        """Calculate annualized returns

        Args:
            nav_data: List of NAV data points
            days_back: Number of days to look back

        Returns:
            Annualized return percentage
        """
        try:
            if len(nav_data) <= days_back:
                logger.debug(f"Insufficient NAV data for {days_back} days calculation")
                return 0.0

            current_nav = float(nav_data[0].get("nav", 0))
            old_nav = float(nav_data[min(days_back, len(nav_data)-1)].get("nav", 0))

            if old_nav == 0:
                logger.warning("Old NAV is zero, cannot calculate returns")
                return 0.0

            years = days_back / 252
            annualized = ((current_nav / old_nav) ** (1 / years) - 1) * 100
            return round(annualized, 2)
        except Exception as e:
            logger.error(f"Error calculating returns: {str(e)}")
            return 0.0

    def _calculate_equity_allocation(self, age: int, risk: str) -> int:
        """Calculate recommended equity allocation

        Args:
            age: Investor's age
            risk: Risk appetite ('aggressive', 'moderate', or 'conservative')

        Returns:
            Recommended equity allocation percentage
        """
        base_equity = max(20, min(90, 100 - age))
        adjustments = {"aggressive": 20, "moderate": 0, "conservative": -20}
        adjustment = adjustments.get(risk.lower(), 0)
        result = max(20, min(90, base_equity + adjustment))
        logger.debug(f"Equity allocation: base={base_equity}%, adjustment={adjustment}%, final={result}%")
        return result

    def _load_fund_list(self) -> List[Dict[str, Any]]:
        """Load mutual fund list with pickle caching for fast startup

        Returns:
            List of all mutual funds from MFApi
        """
        # Create cache directory if it doesn't exist
        cache_dir = Path(".cache")
        cache_dir.mkdir(exist_ok=True)

        pickle_file = cache_dir / "mf_list.pkl"

        # Try loading from pickle first
        if pickle_file.exists():
            try:
                logger.info("Loading mutual fund list from cache...")
                with open(pickle_file, "rb") as f:
                    fund_list = pickle.load(f)
                logger.info(f"✅ Loaded {len(fund_list)} mutual funds from cache (instant)")
                return fund_list
            except Exception as e:
                logger.warning(f"⚠️ Cache load failed: {e}, downloading fresh data...")

        # Download from API if pickle doesn't exist or failed
        try:
            logger.info("Downloading mutual fund list from API... (one-time operation)")
            response = requests.get("https://api.mfapi.in/mf", timeout=15)

            if response.status_code != 200:
                logger.error(f"⚠️ Failed to load fund list: HTTP {response.status_code}")
                return []

            fund_list = response.json()
            logger.info(f"✅ Downloaded {len(fund_list)} mutual funds successfully")

            # Save to pickle for next time
            try:
                with open(pickle_file, "wb") as f:
                    pickle.dump(fund_list, f)
                logger.info(f"💾 Cached fund list to {pickle_file}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cache fund list: {e}")

            return fund_list

        except requests.RequestException as e:
            logger.error(f"⚠️ Network error loading fund list: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"⚠️ Error loading fund list: {str(e)}")
            return []
