"""FinChat Main - ChatGPT-like Financial Assistant"""
from core.query_router import QueryRouter
from agents.user_profile import UserProfileManager

def main():
    print("="*70)
    print("💰 FINCHAT - AI FINANCIAL ASSISTANT")
    print("="*70)
    print("\n✨ Powered by Mistral (LM Studio) + Real-time Market Data\n")
    print("Features:")
    print("  • Natural conversation with AI reasoning")
    print("  • Real-time stocks, mutual funds, ETFs, dividends")
    print("  • Financial calculators (SIP, EMI, retirement)")
    print("  • Tax, investment, insurance guidance")
    print("  • Personalized recommendations")
    print("\n" + "="*70 + "\n")

    # Initialize router
    try:
        router = QueryRouter()
        print("✅ FinChat initialized successfully!\n")
    except Exception as e:
        print(f"⚠️  Warning: {str(e)}")
        print("Note: LM Studio connection will be attempted on first query.\n")
        router = QueryRouter()

    # Get or create user profile
    profile_manager = UserProfileManager()
    user_id = input("Enter your name (or press Enter for 'guest'): ").strip() or "guest"

    existing = profile_manager.load_profile(user_id)
    if not existing:
        print(f"\n👤 Creating profile for {user_id}...")
        try:
            age = int(input("Your age: ") or "30")
            income = float(input("Annual income (₹): ") or "1000000")
            risk = input("Risk appetite (conservative/moderate/aggressive): ").lower() or "moderate"

            profile_manager.create_profile(user_id, {
                "age": age,
                "income": income,
                "risk_appetite": risk
            })
            print("✅ Profile created!\n")
        except ValueError:
            print("Invalid input. Using default profile.\n")
            profile_manager.create_profile(user_id, {
                "age": 30,
                "income": 1000000,
                "risk_appetite": "moderate"
            })
    else:
        print(f"✅ Welcome back, {user_id}!\n")

    print("="*70)
    print("💡 Try asking:")
    print("  • 'What's the current price of HDFC Bank?'")
    print("  • 'Show me top dividend stocks in India'")
    print("  • 'Calculate SIP returns for ₹5000/month for 15 years'")
    print("  • 'Recommend mutual funds for me'")
    print("  • 'How can I save tax under 80C?'")
    print("\nType 'quit' to exit")
    print("="*70 + "\n")

    # Conversation loop
    while True:
        try:
            query = input("You: ").strip()

            if not query:
                continue

            if query.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye! Stay financially savvy!")
                break

            # Process query
            print("\n🤖 FinChat: ", end="", flush=True)
            result = router.handle_query(query, user_id)

            # Print response
            print(result.get("response", "I couldn't process that query."))

            # Save to conversation history
            profile_manager.add_conversation(
                user_id,
                query,
                result.get("response", "")
            )

            print()  # New line for readability

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")

if __name__ == "__main__":
    main()
