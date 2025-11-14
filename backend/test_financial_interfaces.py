import akshare as ak
import pandas as pd

print("Finding available financial interfaces...")

# Test different financial interfaces
interfaces_to_test = [
    'stock_financial_em',
    'stock_balance_sheet_by_report_em', 
    'stock_profit_sheet_by_report_em',
    'stock_cash_flow_sheet_by_report_em',
    'stock_financial_hk_report_em',
    'stock_financial_abstract',
    'stock_financial_analysis_indicator'
]

for interface_name in interfaces_to_test:
    if hasattr(ak, interface_name):
        print(f"✅ Found: {interface_name}")
        try:
            # Test the interface
            interface_func = getattr(ak, interface_name)
            if interface_name in ['stock_financial_em']:
                data = interface_func(symbol='000001', indicator='营业总收入')
            elif interface_name in ['stock_balance_sheet_by_report_em', 'stock_profit_sheet_by_report_em', 'stock_cash_flow_sheet_by_report_em']:
                data = interface_func(symbol='000001')
            else:
                data = interface_func(symbol='000001')
            print(f"   📊 Data shape: {data.shape}")
            print(f"   📋 Columns: {list(data.columns)[:5]}...")
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}...")
    else:
        print(f"❌ Not found: {interface_name}")

print("\nTesting complete!")