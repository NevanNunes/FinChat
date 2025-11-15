# 🤖 FinChat - AI-Powered Financial Assistant

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangChain](https://img.shields.io/badge/LangChain-Enabled-orange.svg)](https://langchain.com/)

**FinChat** is an intelligent financial assistant that helps users with real-time market data, mutual fund analysis, financial calculations, and personalized investment advice. Built with advanced AI techniques including RAG (Retrieval Augmented Generation) and multi-agent architecture.

---

## 🌟 Key Features

### 📊 Real-Time Market Data
- **Live Stock Prices**: Get current prices for NSE-listed stocks (Infosys, TCS, Reliance, HDFC, etc.)
- **Stock Metrics**: Access P/E ratios, dividend yields, and other key metrics
- **ETF Pricing**: Track ETF prices like Nifty BeES, Bank BeES
- **Mutual Fund NAV**: Real-time NAV for 37,000+ mutual funds in India

### 💰 Financial Calculators
- **SIP Calculator**: Calculate returns for Systematic Investment Plans
- **EMI Calculator**: Compute loan EMIs with detailed breakdowns
- **Retirement Planner**: Estimate retirement corpus based on age, expenses, and inflation
- **Lumpsum Investment**: Calculate returns on one-time investments

### 🎯 Smart Investment Recommendations
- **Portfolio Builder**: AI-powered portfolio recommendations based on risk profile
- **Fund Comparison**: Compare mutual funds across categories (Large Cap, Mid Cap, Small Cap, ELSS, etc.)
- **Personalized Advice**: Context-aware suggestions based on user profile and goals

### 📚 Financial Knowledge Base
- **RAG-Powered Q&A**: Ask questions about taxes, insurance, mutual funds, government schemes
- **Semantic Search**: Uses ChromaDB + HuggingFace embeddings for intelligent retrieval
- **Topics Covered**: 80C deductions, capital gains tax, asset allocation, investment strategies, and more

---

## 🏗️ Architecture

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────┐
│                    Query Router                         │
│           (Intelligent Intent Classification)           │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│Market Data   │   │ Calculator   │   │  Knowledge   │
│   Agent      │   │   Agent      │   │  Retriever   │
│ (NSE/MFApi)  │   │  (Finance)   │   │ (RAG+LLM)    │
└──────────────┘   └──────────────┘   └──────────────┘
```

### Core Components

1. **Query Router** (`core/query_router.py`)
   - Regex-based pattern matching for fast routing
   - LLM fallback for complex queries
   - Routes to appropriate agent based on intent

2. **Market Data Agent** (`agents/market_data_agent.py`)
   - NSE stock price fetching
   - Mutual fund data via MFApi
   - Caching for performance

3. **Financial Calculator** (`agents/calculator.py`)
   - SIP/Lumpsum calculations
   - EMI computation
   - Retirement planning with inflation adjustment

4. **Knowledge Retriever** (`core/retriever.py`)
   - ChromaDB vector database
   - HuggingFace embeddings
   - RAG pipeline for financial Q&A

5. **LLM Engine** (`core/llm_engine.py`)
   - OpenAI GPT integration
   - Prompt engineering for financial context
   - Response generation and formatting

---

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- OpenAI API key (optional, for LLM features)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/NevanNunes/FinChat.git
   cd FinChat
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements_new.txt
   ```

3. **Set up environment variables**
   ```bash
   # Create .env file
   echo OPENAI_API_KEY=your_api_key_here > .env
   ```

4. **Run the application**
   ```bash
   # Command-line interface
   python main.py

   # Web interface (Gradio)
   python app.py
   ```

---

## 💡 Usage Examples

### Stock Prices
```
You: What is the Infosys stock price?
FinChat: Infosys (INFY) is currently trading at ₹1,456.30
         Change: +2.34% | P/E Ratio: 28.5
```

### Mutual Fund Search
```
You: Show me top large cap funds
FinChat: Here are the top performing Large Cap funds:
         1. Axis Bluechip Fund - 15.2% (1Y)
         2. ICICI Pru Bluechip Fund - 14.8% (1Y)
         3. Mirae Asset Large Cap - 14.5% (1Y)
```

### SIP Calculator
```
You: Calculate SIP of 5000 for 10 years at 12%
FinChat: 💰 SIP Calculation Results:
         Monthly Investment: ₹5,000
         Investment Period: 10 years
         Expected Return: 12% p.a.
         
         Total Invested: ₹6,00,000
         Estimated Returns: ₹5,49,318
         Maturity Value: ₹11,49,318
```

### Financial Knowledge
```
You: What is Section 80C?
FinChat: Section 80C allows tax deductions up to ₹1.5 lakhs for 
         investments in PPF, ELSS, life insurance premiums, and 
         home loan principal. This helps reduce your taxable income.
```

---

## 📁 Project Structure

```
FinChat/
├── agents/
│   ├── calculator.py          # Financial calculators
│   ├── market_data_agent.py   # Stock & MF data fetching
│   └── user_profile.py        # User profile management
├── core/
│   ├── llm_engine.py          # OpenAI LLM integration
│   ├── query_router.py        # Intent classification & routing
│   └── retriever.py           # RAG + ChromaDB retriever
├── data/
│   ├── static_docs/
│   │   └── financial_knowledge.txt  # Knowledge base
│   └── mf_cache.pkl           # Cached mutual fund data
├── user_profiles/
│   └── *.json                 # User profiles & preferences
├── app.py                     # Gradio web interface
├── main.py                    # CLI interface
├── config.py                  # Configuration settings
└── requirements_new.txt       # Python dependencies
```

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all integration tests
python test_hard_integration.py

# View test results
cat hard_test_results.json
```

Test coverage includes:
- ✅ Stock price fetching (NSE)
- ✅ Mutual fund NAV retrieval
- ✅ SIP/EMI calculations
- ✅ Portfolio recommendations
- ✅ Knowledge retrieval (RAG)
- ✅ Edge cases and error handling

---

## 🔧 Technologies Used

| Technology | Purpose |
|------------|---------|
| **LangChain** | RAG orchestration and LLM chaining |
| **ChromaDB** | Vector database for semantic search |
| **HuggingFace** | Sentence embeddings (all-MiniLM-L6-v2) |
| **OpenAI GPT** | Natural language understanding & generation |
| **Gradio** | Web UI framework |
| **NSE API** | Real-time stock market data |
| **MFApi** | Mutual fund data for India |

---

## 🎓 Key Highlights for Presentation

### 1. **Intelligent Query Routing**
- Hybrid approach: Regex for speed + LLM for accuracy
- No unnecessary LLM calls for simple queries (cost-efficient)

### 2. **RAG Implementation**
- ChromaDB stores financial knowledge as embeddings
- Semantic search finds relevant context
- LLM generates natural answers from retrieved data

### 3. **Real-World Data Integration**
- Live NSE stock prices via YFinance
- 37,000+ mutual funds via MFApi
- Caching to prevent API rate limits

### 4. **Financial Domain Expertise**
- Accurate SIP calculations with compounding
- Retirement planning with inflation modeling
- Tax-aware investment recommendations

### 5. **User Personalization**
- Profile-based recommendations (age, risk tolerance, goals)
- Investment history tracking
- Context-aware responses

---

## 📊 Performance Metrics

- **Query Response Time**: < 2 seconds (average)
- **Mutual Fund Database**: 37,000+ funds
- **Knowledge Base**: 150+ financial topics
- **Test Success Rate**: 87% (41/47 test cases passed)

---

## 🔮 Future Enhancements

- [ ] Multi-language support (Hindi, regional languages)
- [ ] WhatsApp/Telegram bot integration
- [ ] Voice interface
- [ ] Stock portfolio tracker
- [ ] Tax filing assistance
- [ ] Cryptocurrency data integration
- [ ] News sentiment analysis

---

## 📝 Documentation

- **[Tech Deep Dive](TECH_DEEP_DIVE.md)** - Detailed technical explanation
- **[Demo Guide](DEMO_PRESENTATION_GUIDE.md)** - Presentation tips
- **[Stock Price Flow](STOCK_PRICE_FLOW_EXPLAINED.md)** - Data flow diagrams

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Nevan Nunes**

- GitHub: [@NevanNunes](https://github.com/NevanNunes)
- Project Link: [https://github.com/NevanNunes/FinChat](https://github.com/NevanNunes/FinChat)

---

## 🙏 Acknowledgments

- NSE India for stock market data
- MFApi for mutual fund information
- LangChain & ChromaDB communities
- OpenAI for GPT models
- HuggingFace for embeddings

---

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. It does not constitute financial advice. Always consult with a qualified financial advisor before making investment decisions. Past performance does not guarantee future results.

---

<div align="center">
Made with ❤️ for smarter financial decisions
</div>

