"""Manual smoke tests for Stockagents tool integrations."""

from stockagents.tools import (
    CorporateEventsTool,
    NewsAndBuzzTool,
    SocialSentimentTool,
    VolumeAndTechnicalsTool,
)


def run_all_tests() -> None:
    """Execute best-effort integration checks for the tool functions."""
    print("🧪 Running all tool tests...")

    print("\n--- Testing CorporateEventsTool ---")
    msft_result = CorporateEventsTool("MSFT")
    print(f"Result for MSFT: {msft_result}")

    print("\n--- Testing VolumeAndTechnicalsTool ---")
    tsla_technicals = VolumeAndTechnicalsTool("TSLA")
    print(f"Technicals for TSLA: {tsla_technicals}")

    nvda_technicals = VolumeAndTechnicalsTool("NVDA")
    print(f"Technicals for NVDA: {nvda_technicals}")

    print("\n--- Testing NewsAndBuzzTool ---")
    aapl_news = NewsAndBuzzTool("AAPL")
    print(f"News for AAPL: {aapl_news}")
    sources = aapl_news.get("source_breakdown")
    if sources:
        print("Sources breakdown:")
        for item in sources:
            print(f"  - {item.get('source')}: {item.get('count')} articles")
    else:
        print("No additional news sources were returned (fallback to NewsAPI only).")

    print("\n--- Testing SocialSentimentTool ---")
    msft_social = SocialSentimentTool("MSFT")
    print(f"Social sentiment for MSFT: {msft_social}")


if __name__ == "__main__":
    run_all_tests()
