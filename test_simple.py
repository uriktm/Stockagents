"""Simple test to debug the issue."""

import sys
import logging
import traceback
from stockagents import run_stock_analysis, parse_symbols

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("Starting Stockagents Analysis Test")
    print("=" * 60)
    
    try:
        symbols = parse_symbols("AAPL")
        print(f"\n✓ Parsed symbols: {symbols}")
        
        print("\n🔄 Running analysis (this may take 30-60 seconds)...\n")
        results = run_stock_analysis(symbols)
        
        print("\n" + "=" * 60)
        print(f"✓ Received {len(results)} results")
        print("=" * 60)
        
        for result in results:
            print(f"\n📊 Symbol: {result.get('symbol')}")
            print(f"   Confidence: {result.get('confidence_score')}")
            print(f"   Forecast: {result.get('forecast')}")
            
            if 'error' in result:
                print(f"   ❌ Error: {result.get('error')}")
            else:
                print(f"   ✓ Analysis completed successfully")
                
            # Show a snippet of the full response
            response = result.get('response_text', '')
            if response:
                print(f"\n   Response preview (first 200 chars):")
                print(f"   {response[:200]}...")
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
