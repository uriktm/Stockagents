# tests.py

# ייבוא הכלים שאנחנו רוצים לבדוק מהקובץ tools.py
from tools import CorporateEventsTool, VolumeAndTechnicalsTool, NewsAndBuzzTool

def run_all_tests():
    """
    פונקציה זו מריצה את כל הבדיקות עבור הכלים שלנו.
    """
    print("🧪 Running all tool tests...")

    # --- בדיקה 1: CorporateEventsTool ---
    print("\n--- Testing CorporateEventsTool ---")
    msft_result = CorporateEventsTool('MSFT')
    print(f"Result for MSFT: {msft_result}")

    # --- בדיקה 2: VolumeAndTechnicalsTool ---
    print("\n--- Testing VolumeAndTechnicalsTool ---")
    tsla_technicals = VolumeAndTechnicalsTool('TSLA')
    print(f"Technicals for TSLA: {tsla_technicals}")

    nvda_technicals = VolumeAndTechnicalsTool('NVDA')
    print(f"Technicals for NVDA: {nvda_technicals}")

    # --- בדיקה 3: NewsAndBuzzTool ---
    print("\n--- Testing NewsAndBuzzTool ---")
    aapl_news = NewsAndBuzzTool('AAPL')
    print(f"News for AAPL: {aapl_news}")
    sources = aapl_news.get("source_breakdown")
    if sources:
        print("Sources breakdown:")
        for item in sources:
            print(f"  - {item.get('source')}: {item.get('count')} articles")
    else:
        print("No additional news sources were returned (fallback to NewsAPI only).")

# הרצת הבדיקות כאשר מריצים את הקובץ ישירות
if __name__ == "__main__":
    run_all_tests()