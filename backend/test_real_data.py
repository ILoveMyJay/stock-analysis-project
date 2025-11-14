import sys
sys.path.append('.')

from main import get_real_fundamental_data_with_cache, clean_expired_cache

# 清理过期缓存
clean_expired_cache()

print("Testing real data fetch for a new stock...")

# 测试一个新的股票代码
test_codes = ['000002', '000858', '002594']

for code in test_codes:
    print(f"\n{'='*50}")
    print(f"Testing stock: {code}")
    print(f"{'='*50}")
    
    try:
        data = get_real_fundamental_data_with_cache(code)
        print(f"Stock: {data['stock_name']} ({data['stock_code']})")
        print(f"PE Ratio: {data['pe_ratio']}")
        print(f"Revenue Growth: {data['revenue_growth']}%")
        print(f"ROE: {data['roe']}%")
        print(f"Debt Ratio: {data['debt_ratio']}%")
        print(f"Data Source: {data['data_source']}")
        print(f"Data Period: {data.get('data_period', 'N/A')}")
        
        # 检查是否是真实数据
        if data['pe_ratio'] != 20.0 or data['revenue_growth'] != 10.0:
            print("✅ SUCCESS: Got real data!")
        else:
            print("⚠️  WARNING: Still using default values")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    break  # 只测试第一个