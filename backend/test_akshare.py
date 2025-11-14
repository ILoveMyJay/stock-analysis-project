import akshare as ak
import pandas as pd

print("Testing AKShare interfaces...")

# Test 1: Basic info
try:
    print("\n1. Testing basic info...")
    basic_info = ak.stock_individual_info_em(symbol='000001')
    print(f"✅ Basic info OK: {len(basic_info)} records")
    print(basic_info.head())
except Exception as e:
    print(f"❌ Basic info failed: {e}")

# Test 2: Financial indicators  
try:
    print("\n2. Testing financial indicators...")
    financial_data = ak.stock_a_indicator_lg(symbol='000001')
    print(f"✅ Financial indicators OK: {len(financial_data)} records")
    print(financial_data.head())
except Exception as e:
    print(f"❌ Financial indicators failed: {e}")

# Test 3: Valuation data
try:
    print("\n3. Testing valuation data...")
    valuation_data = ak.stock_zh_valuation_baidu(symbol='000001')
    print(f"✅ Valuation data OK: {len(valuation_data)} records")
    print(valuation_data.head())
except Exception as e:
    print(f"❌ Valuation data failed: {e}")

# Test 4: Quarterly financial data
try:
    print("\n4. Testing quarterly data...")
    quarterly_data = ak.stock_financial_abstract_ths(symbol='000001', indicator="营业收入")
    print(f"✅ Quarterly data OK: {len(quarterly_data)} records")
    print(quarterly_data.head())
except Exception as e:
    print(f"❌ Quarterly data failed: {e}")

print("\nTesting complete!")