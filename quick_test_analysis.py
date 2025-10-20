#!/usr/bin/env python3
"""Quick test to analyze a single stock and see detailed logs."""

import logging
import sys
from pathlib import Path

# Setup logging to see everything
# Ensure logs directory exists
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / 'quick_test.log', encoding='utf-8', mode='w')
    ]
)

from stockagents import run_stock_analysis

if __name__ == "__main__":
    print("🔍 Running quick analysis test...")
    print("=" * 60)
    
    # Test with one stock that should have good data
    test_symbols = ["AAPL"]
    
    print(f"\n📊 Analyzing: {', '.join(test_symbols)}\n")
    
    try:
        results = run_stock_analysis(test_symbols)
        
        print("\n" + "=" * 60)
        print("📋 RESULTS:")
        print("=" * 60)
        
        for result in results:
            symbol = result.get('symbol', 'Unknown')
            forecast = result.get('forecast', 'NOT FOUND')
            confidence = result.get('confidence_score', 'NOT FOUND')
            
            print(f"\n🏢 {symbol}:")
            print(f"  📈 Forecast: {forecast[:100] if forecast else 'N/A'}...")
            print(f"  🎯 Confidence: {confidence}")
            
            # Show tool insights
            insights = result.get('tool_insights', {})
            technicals = insights.get('technicals', {})
            news = insights.get('news', {})
            
            print(f"\n  📊 Technical Data:")
            print(f"    - RSI: {technicals.get('rsi', 'N/A')}")
            print(f"    - Volume Ratio: {technicals.get('volume_spike_ratio', 'N/A')}")
            print(f"    - Signal: {technicals.get('technical_signal', 'N/A')}")
            
            print(f"\n  📰 News Data:")
            print(f"    - Sentiment: {news.get('sentiment_score', 'N/A')}")
            print(f"    - Buzz Factor: {news.get('buzz_factor', 'N/A')}")
            print(f"    - Articles: {news.get('source_count', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("✅ Analysis complete!")
        print(f"📄 Full logs saved to: logs/quick_test.log")
        print(f"📄 Detailed logs in: logs/detailed_analysis.log")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
