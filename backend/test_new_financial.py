import akshare as ak
import pandas as pd

print("Testing new financial data extraction...")

stock_code = '000001'
print(f"Testing stock: {stock_code}")

try:
    # 获取财务摘要数据
    financial_abstract = ak.stock_financial_abstract(symbol=stock_code)
    print(f"Financial abstract shape: {financial_abstract.shape}")
    
    if not financial_abstract.empty:
        print("\nAvailable indicators:")
        print(financial_abstract['指标'].tolist()[:20])  # 显示前20个指标
        
        # 查找关键指标
        pe_data = financial_abstract[financial_abstract['指标'].str.contains('P/E|市盈率', na=False)]
        pb_data = financial_abstract[financial_abstract['指标'].str.contains('市净率|P/B', na=False)]
        roe_data = financial_abstract[financial_abstract['指标'].str.contains('ROE|净资产收益率', na=False)]
        debt_data = financial_abstract[financial_abstract['指标'].str.contains('资产负债率', na=False)]
        
        print(f"\nPE data found: {len(pe_data)} records")
        if not pe_data.empty:
            print(pe_data)
            
        print(f"\nPB data found: {len(pb_data)} records")
        if not pb_data.empty:
            print(pb_data.head())
            
        print(f"\nROE data found: {len(roe_data)} records")
        if not roe_data.empty:
            print(roe_data.head())
            
        print(f"\nDebt data found: {len(debt_data)} records")
        if not debt_data.empty:
            print(debt_data.head())
            
        # 获取最新一期数据列
        if len(financial_abstract.columns) > 2:
            latest_col = financial_abstract.columns[2]
            print(f"\nLatest data column: {latest_col}")
            
            # 尝试提取具体数值
            if not pe_data.empty:
                pe_value = pe_data.iloc[0][latest_col]
                print(f"PE value: {pe_value}")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()