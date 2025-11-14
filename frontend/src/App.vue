<template>
  <div id="app">
    <header>
      <h1>股票分析工具</h1>
      <div class="search-bar">
        <input 
          v-model="stockInput" 
          @keyup.enter="addStock"
          placeholder="输入股票代码或名称后按回车"
        />
        <button @click="addStock">添加股票</button>
      </div>
    </header>

    <div class="app-layout">
      <!-- 左侧导航栏 -->
      <aside class="sidebar" v-if="stocks.length > 0">
        <h3>股票列表</h3>
        <div class="stock-nav">
          <div 
            v-for="stock in stocks" 
            :key="stock.stock_code" 
            class="nav-item"
            :class="{ 'active': activeStock === stock.stock_code }"
            @click="scrollToStock(stock.stock_code)"
          >
            <div class="nav-stock-info">
              <span class="nav-stock-name" :class="{ 'highlight': stock.highlight }">
                {{ stock.stock_name }}
              </span>
              <span class="nav-stock-code">{{ stock.stock_code }}</span>
            </div>
            <div class="nav-signals" v-if="stock.strategies">
              <span 
                v-for="(strategy, key) in getMainSignals(stock.strategies)" 
                :key="key"
                :class="['signal-dot', `signal-${strategy}`]"
                :title="key"
              ></span>
            </div>
          </div>
        </div>
      </aside>
      
      <!-- 主内容区域 -->
      <main class="main-content">
        <div v-if="isLoading" class="loading">正在加载数据...</div>
        <div v-if="error" class="error">{{ error }}</div>

      <div v-for="stock in stocks" :key="stock.stock_code" class="stock-card" :id="`stock-${stock.stock_code}`">
        <div class="stock-header">
          <h2 :class="{ 'highlight': stock.highlight }">
            {{ stock.stock_name }} ({{ stock.stock_code }})
          </h2>
          <button @click="removeStock(stock.stock_code)" class="remove-btn">删除</button>
        </div>
        
        <!-- 策略分析结果 -->
        <div v-if="stock.strategies" class="strategies-panel">
          <h3>策略分析结果</h3>
          <div class="strategies-grid">
            <!-- 高亮策略 -->
            <div class="strategy-item">
              <span class="strategy-name">高亮策略:</span>
              <span :class="['strategy-result', stock.strategies.highlight_strategy?.result ? 'positive' : 'negative']">
                {{ stock.strategies.highlight_strategy?.result ? '符合' : '不符合' }}
              </span>
            </div>
            
            <!-- 双均线策略 -->
            <div class="strategy-item" v-if="stock.strategies.ma_crossover">
              <span class="strategy-name">双均线:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.ma_crossover.signal}`]">
                {{ getSignalText(stock.strategies.ma_crossover.signal) }}
              </span>
              <span class="strategy-detail">
                ({{ stock.strategies.ma_crossover.current_trend === 'bullish' ? '上升趋势' : '下降趋势' }})
              </span>
            </div>
            
            <!-- MACD策略 -->
            <div class="strategy-item" v-if="stock.strategies.macd">
              <span class="strategy-name">MACD:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.macd.signal}`]">
                {{ getSignalText(stock.strategies.macd.signal) }}
              </span>
              <span class="strategy-detail">
                ({{ stock.strategies.macd.current_trend === 'bullish' ? '多头' : '空头' }})
              </span>
            </div>
            
            <!-- RSI策略 -->
            <div class="strategy-item" v-if="stock.strategies.rsi">
              <span class="strategy-name">RSI:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.rsi.signal}`]">
                {{ getSignalText(stock.strategies.rsi.signal) }}
              </span>
              <span class="strategy-detail">
                ({{ stock.strategies.rsi.rsi?.toFixed(1) }}, {{ getRSILevelText(stock.strategies.rsi.current_level) }})
              </span>
            </div>
            
            <!-- 布林带策略 -->
            <div class="strategy-item" v-if="stock.strategies.bollinger_bands">
              <span class="strategy-name">布林带:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.bollinger_bands.signal}`]">
                {{ getSignalText(stock.strategies.bollinger_bands.signal) }}
              </span>
              <span class="strategy-detail">
                (位置: {{ getBollingerPositionText(stock.strategies.bollinger_bands.current_position) }})
              </span>
            </div>
            
            <!-- 动量策略 -->
            <div class="strategy-item" v-if="stock.strategies.momentum">
              <span class="strategy-name">动量策略:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.momentum.signal}`]">
                {{ getSignalText(stock.strategies.momentum.signal) }}
              </span>
              <span class="strategy-detail">
                ({{ stock.strategies.momentum.momentum_percentage?.toFixed(1) }}%, {{ getMomentumStrengthText(stock.strategies.momentum.momentum_strength) }})
              </span>
            </div>
            
            <!-- 突破策略 -->
            <div class="strategy-item" v-if="stock.strategies.breakout">
              <span class="strategy-name">突破策略:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.breakout.signal}`]">
                {{ getSignalText(stock.strategies.breakout.signal) }}
              </span>
              <span class="strategy-detail">
                ({{ getBreakoutTypeText(stock.strategies.breakout.breakout_type) }}, 量比: {{ stock.strategies.breakout.volume_ratio?.toFixed(1) }}x)
              </span>
            </div>
            
            <!-- PEG策略 -->
            <div class="strategy-item clickable" v-if="stock.strategies.peg" @click="showPEGDetail(stock)">
              <span class="strategy-name">PEG策略:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.peg.signal}`]">
                {{ getSignalText(stock.strategies.peg.signal) }}
              </span>
              <span class="strategy-detail">
                (PEG: {{ stock.strategies.peg.peg_value }}, {{ getPEGValuationText(stock.strategies.peg.valuation) }})
              </span>
              <span class="detail-hint">💡 点击查看详情</span>
            </div>
            
            <!-- 价值因子策略 -->
            <div class="strategy-item" v-if="stock.strategies.value_factor">
              <span class="strategy-name">价值因子:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.value_factor.signal}`]">
                {{ getSignalText(stock.strategies.value_factor.signal) }}
              </span>
              <span class="strategy-detail">
                (综合评分: {{ stock.strategies.value_factor.total_score }}, {{ getValueLevelText(stock.strategies.value_factor.value_level) }})
              </span>
            </div>
            
            <!-- 财务健康策略 -->
            <div class="strategy-item clickable" v-if="stock.strategies.financial_health" @click="showFinancialHealthDetail(stock)">
              <span class="strategy-name">财务健康:</span>
              <span :class="['strategy-signal', `signal-${stock.strategies.financial_health.signal}`]">
                {{ getSignalText(stock.strategies.financial_health.signal) }}
              </span>
              <span class="strategy-detail">
                (健康评分: {{ stock.strategies.financial_health.health_score }}, {{ getHealthLevelText(stock.strategies.financial_health.health_level) }})
              </span>
              <span class="detail-hint">💡 点击查看详情</span>
            </div>
          </div>
        </div>
        
        <div class="chart-container" :ref="el => setChartRef(el, stock.stock_code)"></div>
      </div>

      <div v-if="!stocks.length && !isLoading" class="no-data">
        请在上方输入框添加股票进行分析
      </div>
      </main>
    </div>
    
    <!-- 财务健康详情弹窗 -->
    <div v-if="showHealthModal" class="modal-overlay" @click="closeHealthModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>财务健康策略详情</h3>
          <button @click="closeHealthModal" class="close-btn">&times;</button>
        </div>
        
        <div class="modal-body" v-if="selectedStock">
          <div class="stock-info">
            <h4>{{ selectedStock.stock_name }} ({{ selectedStock.stock_code }})</h4>
            <div class="overall-score">
              <span class="score-label">综合健康评分:</span>
              <span class="score-value">{{ selectedStock.strategies.financial_health.health_score }}/100</span>
              <span :class="['health-level', `level-${selectedStock.strategies.financial_health.health_level}`]">
                {{ getHealthLevelText(selectedStock.strategies.financial_health.health_level) }}
              </span>
            </div>
          </div>
          
          <div class="scoring-details">
            <h5>评分细分:</h5>
            <div class="score-breakdown">
              <div class="score-item">
                <span class="metric-name">资产负债率 (30%)</span>
                <div class="metric-info">
                  <span class="metric-value">{{ selectedStock.strategies.financial_health.debt_ratio }}%</span>
                  <span class="metric-score">{{ selectedStock.strategies.financial_health.sub_scores.debt_score }}/30分</span>
                </div>
                <div class="metric-calculation">
                  <small>计算公式: 资产负债率 = (负债总计 ÷ 资产总计) × 100%</small>
                  <small>风险评估: 负债率越低，财务风险越小，健康程度越高</small>
                </div>
              </div>
              
              <div class="score-item">
                <span class="metric-name">ROE收益率 (25%)</span>
                <div class="metric-info">
                  <span class="metric-value">{{ selectedStock.strategies.financial_health.roe }}%</span>
                  <span class="metric-score">{{ selectedStock.strategies.financial_health.sub_scores.roe_score }}/25分</span>
                </div>
                <div class="metric-calculation">
                  <small>计算公式: ROE = (净利润 ÷ 股东权益) × 100%</small>
                  <small>盈利能力: ROE越高，表示公司使用股东资金创造利润的能力越强</small>
                </div>
              </div>
              
              <div class="score-item">
                <span class="metric-name">增长稳定性 (25%)</span>
                <div class="metric-info">
                  <span class="metric-value">{{ selectedStock.strategies.financial_health.revenue_growth }}%</span>
                  <span v-if="selectedStock.strategies.financial_health.semi_annual_growth" class="metric-value-extra">
                    (半年度: {{ selectedStock.strategies.financial_health.semi_annual_growth }}%)
                  </span>
                  <span class="metric-score">{{ selectedStock.strategies.financial_health.sub_scores.growth_score }}/25分</span>
                </div>
                <div class="metric-calculation">
                  <small>计算公式: 增长率 = ((本期营收 - 同期营收) ÷ 同期营收) × 100%</small>
                  <small>成长性: 正向增长表示公司业务扩张，增长率越高越好</small>
                </div>
                <div class="metric-period">
                  <small>数据周期: {{ selectedStock.strategies.financial_health.growth_period || '年度同比' }}</small>
                </div>
              </div>
              
              <div class="score-item">
                <span class="metric-name">市值规模 (20%)</span>
                <div class="metric-info">
                  <span class="metric-value">{{ selectedStock.strategies.financial_health.market_cap }}亿元</span>
                  <span class="metric-score">{{ selectedStock.strategies.financial_health.sub_scores.size_score }}/20分</span>
                </div>
                <div class="metric-calculation">
                  <small>计算公式: 市值 = 股价 × 流通股本</small>
                  <small>规模效应: 大市值公司通常具有更强的抗风险能力和稳定性</small>
                </div>
              </div>
            </div>
          </div>
          
          <div class="scoring-criteria">
            <h5>评分标准:</h5>
            <div class="criteria-grid">
              <div class="criteria-section">
                <h6>资产负债率</h6>
                <ul>
                  <li>&lt;30%: 30分</li>
                  <li>30-50%: 20分</li>
                  <li>50-70%: 10分</li>
                  <li>&gt;70%: 0分</li>
                </ul>
              </div>
              
              <div class="criteria-section">
                <h6>ROE收益率</h6>
                <ul>
                  <li>&gt;20%: 25分</li>
                  <li>15-20%: 20分</li>
                  <li>10-15%: 15分</li>
                  <li>5-10%: 10分</li>
                  <li>&lt;5%: 0分</li>
                </ul>
              </div>
              
              <div class="criteria-section">
                <h6>增长稳定性</h6>
                <ul>
                  <li>&gt;20%: 25分</li>
                  <li>10-20%: 20分</li>
                  <li>5-10%: 15分</li>
                  <li>0-5%: 10分</li>
                  <li>&lt;0%: 0分</li>
                </ul>
              </div>
              
              <div class="criteria-section">
                <h6>市值规模</h6>
                <ul>
                  <li>&gt;1000亿: 20分</li>
                  <li>500-1000亿: 15分</li>
                  <li>100-500亿: 10分</li>
                  <li>50-100亿: 5分</li>
                  <li>&lt;50亿: 0分</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div class="health-levels">
            <h5>健康等级划分:</h5>
            <div class="level-list">
              <div class="level-item level-excellent">85-100分: 优秀 (买入)</div>
              <div class="level-item level-good">65-84分: 良好 (买入)</div>
              <div class="level-item level-fair">50-64分: 一般 (持有)</div>
              <div class="level-item level-poor">30-49分: 较差 (卖出)</div>
              <div class="level-item level-very_poor">&lt;30分: 很差 (卖出)</div>
            </div>
          </div>
          
          <div class="data-source">
            <div class="data-info">
              <small>数据来源: {{ selectedStock.strategies.financial_health.data_source }}</small>
              <small v-if="selectedStock.strategies.financial_health.data_period">
                数据周期: {{ selectedStock.strategies.financial_health.data_period === 'quarterly_and_semi_annual' ? '季度+半年度(更及时)' : '年度数据' }}
              </small>
              <small v-if="selectedStock.strategies.financial_health.last_update">
                更新时间: {{ selectedStock.strategies.financial_health.last_update }}
              </small>
            </div>
            <div class="data-advantage" v-if="selectedStock.strategies.financial_health.data_period === 'quarterly_and_semi_annual'">
              <span class="advantage-badge">✨ 使用最新季度数据，更加及时</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- PEG策略详情弹窗 -->
    <div v-if="showPEGModal" class="modal-overlay" @click="closePEGModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>PEG策略详情</h3>
          <button @click="closePEGModal" class="close-btn">&times;</button>
        </div>
        
        <div class="modal-body" v-if="selectedStock && selectedStock.strategies.peg">
          <div class="stock-info">
            <h4>{{ selectedStock.stock_name }} ({{ selectedStock.stock_code }})</h4>
            <div class="overall-score">
              <span class="score-label">PEG指标:</span>
              <span class="score-value">{{ selectedStock.strategies.peg.peg_value || 'N/A' }}</span>
              <span :class="['peg-level', `level-${selectedStock.strategies.peg.valuation}`]">
                {{ getPEGValuationText(selectedStock.strategies.peg.valuation) }}
              </span>
            </div>
          </div>
          
          <div class="peg-calculation">
            <h5>PEG计算公式:</h5>
            <div class="formula-box">
              <div class="formula">PEG = PE率 ÷ 增长率</div>
              <div class="calculation">
                PEG = {{ selectedStock.strategies.peg.pe_ratio }} ÷ {{ selectedStock.strategies.peg.growth_rate }}% = {{ selectedStock.strategies.peg.peg_value }}
              </div>
            </div>
          </div>
          
          <div class="peg-components">
            <h5>组成数据:</h5>
            <div class="component-grid">
              <div class="component-item">
                <span class="component-label">PE市盈率:</span>
                <span class="component-value">{{ selectedStock.strategies.peg.pe_ratio }}</span>
              </div>
              <div class="component-item">
                <span class="component-label">营收增长率:</span>
                <span class="component-value">{{ selectedStock.strategies.peg.growth_rate }}%</span>
              </div>
              <div class="component-item">
                <span class="component-label">市值规模:</span>
                <span class="component-value">{{ selectedStock.strategies.peg.market_cap }}亿元</span>
              </div>
              <div class="component-item">
                <span class="component-label">所属行业:</span>
                <span class="component-value">{{ selectedStock.strategies.peg.industry || '未知' }}</span>
              </div>
            </div>
          </div>
          
          <div class="peg-analysis">
            <h5>PEG指标分析:</h5>
            <div class="analysis-grid">
              <div class="analysis-section">
                <h6>估值水平</h6>
                <ul>
                  <li><strong>PEG < 0.5</strong>: 严重低估 (强烈买入)</li>
                  <li><strong>0.5 ≤ PEG < 1.0</strong>: 低估 (买入)</li>
                  <li><strong>1.0 ≤ PEG < 1.5</strong>: 合理 (持有)</li>
                  <li><strong>1.5 ≤ PEG < 2.0</strong>: 高估 (卖出)</li>
                  <li><strong>PEG ≥ 2.0</strong>: 严重高估 (强烈卖出)</li>
                </ul>
              </div>
              
              <div class="analysis-section">
                <h6>投资逻辑</h6>
                <ul>
                  <li>彼得·林奇的经典指标</li>
                  <li>综合考虑估值和成长性</li>
                  <li>适用于成长型公司</li>
                  <li>避免单纯PE的局限性</li>
                </ul>
              </div>
              
              <div class="analysis-section">
                <h6>使用限制</h6>
                <ul>
                  <li>不适用于负增长公司</li>
                  <li>对周期性行业可能失真</li>
                  <li>需要结合其他指标分析</li>
                  <li>增长率预测存在不确定性</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div class="peg-strategy-result">
            <h5>策略结论:</h5>
            <div class="result-box">
              <div class="result-signal">
                <span class="signal-label">投资建议:</span>
                <span :class="['strategy-signal', `signal-${selectedStock.strategies.peg.signal}`]">
                  {{ getSignalText(selectedStock.strategies.peg.signal) }}
                </span>
              </div>
              <div class="result-reason">
                <span class="reason-label">分析原因:</span>
                <span class="reason-text">{{ selectedStock.strategies.peg.reason }}</span>
              </div>
            </div>
          </div>
          
          <div class="data-source">
            <div class="data-info">
              <small>数据来源: {{ selectedStock.strategies.peg.data_source }}</small>
              <small v-if="selectedStock.strategies.peg.last_update">
                更新时间: {{ selectedStock.strategies.peg.last_update }}
              </small>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import axios from 'axios';
import * as echarts from 'echarts';

const stockInput = ref('');
const stocks = ref([]);
const isLoading = ref(false);
const error = ref(null);
const activeStock = ref(''); // 当前激活的股票
const showHealthModal = ref(false); // 财务健康弹窗显示状态
const showPEGModal = ref(false); // PEG策略弹窗显示状态
const selectedStock = ref(null); // 选中的股票数据

const chartRefs = ref({});
const chartInstances = ref({});

const setChartRef = (el, stockCode) => {
  if (el) {
    chartRefs.value[stockCode] = el;
  }
};

const addStock = async () => {
  if (!stockInput.value.trim()) return;
  const stockCode = stockInput.value.trim();
  
  // 检查是否已存在
  if (stocks.value.some(s => s.stock_code === stockCode)) {
    error.value = `股票 ${stockCode} 已经存在了。`;
    return;
  }

  isLoading.value = true;
  error.value = null;

  try {
    const response = await axios.get(`/api/stock/${stockCode}`);
    stocks.value.push(response.data);
    stockInput.value = ''; // 清空输入框

    // 等待 DOM 更新后渲染图表
    await nextTick();
    renderChart(response.data);

  } catch (err) {
    if (err.response) {
      error.value = `错误: ${err.response.data.detail || '无法获取股票数据'}`;
    } else {
      error.value = '无法连接到后端服务，请确保后端服务已启动。';
    }
    console.error(err);
  } finally {
    isLoading.value = false;
  }
};

const removeStock = async (stockCode) => {
  try {
    await axios.delete(`/api/stock/${stockCode}`);
    // 从前端列表中移除
    stocks.value = stocks.value.filter(s => s.stock_code !== stockCode);
    // 销毁图表实例
    if (chartInstances.value[stockCode]) {
      chartInstances.value[stockCode].dispose();
      delete chartInstances.value[stockCode];
    }
  } catch (err) {
    error.value = `删除失败: ${err.response?.data?.detail || '未知错误'}`;
  }
};

const loadSavedStocks = async () => {
  try {
    const response = await axios.get('/api/stocks');
    const savedStocks = response.data.stocks;
    
    for (const savedStock of savedStocks) {
      // 获取最新数据
      try {
        const stockResponse = await axios.get(`/api/stock/${savedStock.stock_code}`);
        stocks.value.push(stockResponse.data);
        await nextTick();
        renderChart(stockResponse.data);
      } catch (stockErr) {
        console.warn(`无法加载股票 ${savedStock.stock_code}:`, stockErr);
      }
    }
  } catch (err) {
    console.warn('无法加载已保存的股票:', err);
  }
};

// 辅助函数
const getSignalText = (signal) => {
  const signalMap = {
    'buy': '买入',
    'sell': '卖出', 
    'hold': '持有',
    'insufficient_data': '数据不足'
  };
  return signalMap[signal] || signal;
};

const getRSILevelText = (level) => {
  const levelMap = {
    'oversold': '超卖',
    'overbought': '超买',
    'normal': '正常',
    'unknown': '未知'
  };
  return levelMap[level] || level;
};

const getBollingerPositionText = (position) => {
  const positionMap = {
    'upper': '上轨',
    'lower': '下轨',
    'middle': '中轨',
    'upper_middle': '中上',
    'lower_middle': '中下',
    'unknown': '未知'
  };
  return positionMap[position] || position;
};

// 导航相关函数
const scrollToStock = (stockCode) => {
  const element = document.getElementById(`stock-${stockCode}`);
  if (element) {
    element.scrollIntoView({ 
      behavior: 'smooth', 
      block: 'start' 
    });
    activeStock.value = stockCode;
    // 2秒后清除激活状态
    setTimeout(() => {
      activeStock.value = '';
    }, 2000);
  }
};

// 获取主要信号用于导航显示
const getMainSignals = (strategies) => {
  const mainStrategies = ['ma_crossover', 'macd', 'rsi', 'bollinger_bands'];
  const signals = {};
  
  mainStrategies.forEach(strategy => {
    if (strategies[strategy] && strategies[strategy].signal) {
      signals[strategy] = strategies[strategy].signal;
    }
  });
  
  return signals;
};

// 新增的辅助函数
const getMomentumStrengthText = (strength) => {
  const strengthMap = {
    'very_weak': '极弱',
    'weak': '弱势',
    'normal': '正常',
    'moderate': '中等',
    'strong': '强势',
    'unknown': '未知'
  };
  return strengthMap[strength] || strength;
};

const getBreakoutTypeText = (type) => {
  const typeMap = {
    'upward_breakout': '向上突破',
    'downward_breakout': '向下突破',
    'potential_breakout': '潜在突破',
    'none': '无突破',
    'unknown': '未知'
  };
  return typeMap[type] || type;
};

const getPEGValuationText = (valuation) => {
  const valuationMap = {
    'very_undervalued': '严重低估',
    'undervalued': '低估',
    'fair': '合理',
    'overvalued': '高估',
    'very_overvalued': '严重高估',
    'negative_growth': '负增长',
    'unknown': '未知'
  };
  return valuationMap[valuation] || valuation;
};

const getValueLevelText = (level) => {
  const levelMap = {
    'excellent': '优秀',
    'good': '良好',
    'fair': '一般',
    'poor': '较差',
    'very_poor': '很差',
    'unknown': '未知'
  };
  return levelMap[level] || level;
};

const getHealthLevelText = (level) => {
  const levelMap = {
    'excellent': '非常健康',
    'good': '健康',
    'fair': '一般',
    'poor': '较差',
    'very_poor': '很差',
    'unknown': '未知'
  };
  return levelMap[level] || level;
};

// 显示财务健康详情
const showFinancialHealthDetail = (stock) => {
  selectedStock.value = stock;
  showHealthModal.value = true;
};

// 关闭财务健康弹窗
const closeHealthModal = () => {
  showHealthModal.value = false;
  selectedStock.value = null;
};

// 显示PEG详情
const showPEGDetail = (stock) => {
  selectedStock.value = stock;
  showPEGModal.value = true;
};

// 关闭PEG弹窗
const closePEGModal = () => {
  showPEGModal.value = false;
  selectedStock.value = null;
};

const renderChart = (stockData) => {
  const chartDom = chartRefs.value[stockData.stock_code];
  if (!chartDom) return;

  // 如果已经有实例，先销毁
  if (chartInstances.value[stockData.stock_code]) {
    chartInstances.value[stockData.stock_code].dispose();
  }

  const myChart = echarts.init(chartDom);
  chartInstances.value[stockData.stock_code] = myChart;

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        height: '50%'
      },
      {
        left: '10%',
        right: '8%',
        top: '65%',
        height: '15%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: stockData.k_line_data.map(item => item[0]),
        axisLine: { onZero: false },
        splitLine: { show: false },
        axisLabel: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: stockData.volume_data.map(item => item[0]),
        axisLabel: {
            formatter: function (value) {
                return echarts.format.formatTime('yyyy-MM-dd', value);
            }
        }
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true
        }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 70,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        top: '90%',
        start: 70,
        end: 100
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: stockData.k_line_data.map(item => [item[1], item[2], item[3], item[4]]),
        itemStyle: {
          color: '#ec0000',
          color0: '#00da3c',
          borderColor: '#8A0000',
          borderColor0: '#008F28'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: stockData.volume_data.map(item => item[1]),
        itemStyle: {
            color: (params) => {
                // 根据当天K线的涨跌决定成交量柱子的颜色
                const kLineDataPoint = stockData.k_line_data[params.dataIndex];
                // kLineDataPoint[1] 是开盘价, kLineDataPoint[2] 是收盘价
                return kLineDataPoint[2] >= kLineDataPoint[1] ? '#ec0000' : '#00da3c';
            }
        }
      }
    ]
  };

  myChart.setOption(option);
};

// 可以在这里预加载一个股票
onMounted(() => {
    // 加载已保存的股票
    loadSavedStocks();
});
</script>

<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: #f4f7f9;
  color: #333;
  margin: 0;
  padding: 20px;
}

#app {
  max-width: 1400px;
  margin: 0 auto;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  padding: 20px;
}

.app-layout {
  display: flex;
  gap: 20px;
  min-height: 600px;
}

/* 左侧导航栏 */
.sidebar {
  width: 300px;
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #e9ecef;
  max-height: 80vh;
  overflow-y: auto;
  position: sticky;
  top: 20px;
}

.sidebar h3 {
  margin: 0 0 15px 0;
  color: #495057;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 2px solid #dee2e6;
  padding-bottom: 10px;
}

.stock-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #dee2e6;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-item:hover {
  border-color: #adb5bd;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.nav-item.active {
  border-color: #007bff;
  background-color: #e3f2fd;
  box-shadow: 0 2px 8px rgba(0,123,255,0.2);
}

.nav-stock-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-stock-name {
  font-weight: 600;
  font-size: 14px;
  color: #495057;
}

.nav-stock-name.highlight {
  color: #e67e22;
}

.nav-stock-code {
  font-size: 12px;
  color: #6c757d;
}

.nav-signals {
  display: flex;
  gap: 4px;
}

.signal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1px solid #ccc;
}

.signal-dot.signal-buy {
  background-color: #28a745;
  border-color: #1e7e34;
}

.signal-dot.signal-sell {
  background-color: #dc3545;
  border-color: #c82333;
}

.signal-dot.signal-hold {
  background-color: #ffc107;
  border-color: #e0a800;
}

.signal-dot.signal-insufficient_data {
  background-color: #6c757d;
  border-color: #545b62;
}

/* 主内容区域 */
.main-content {
  flex: 1;
  min-width: 0;
}

header {
  border-bottom: 2px solid #eee;
  padding-bottom: 20px;
  margin-bottom: 20px;
}

h1 {
  text-align: center;
  color: #2c3e50;
}

.search-bar {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.search-bar input {
  width: 300px;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 16px;
}

.search-bar button {
  padding: 10px 20px;
  border: none;
  background-color: #42b983;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.search-bar button:hover {
  background-color: #36a374;
}

.loading, .error, .no-data {
  text-align: center;
  padding: 40px;
  font-size: 18px;
  color: #666;
}

.error {
  color: #e74c3c;
}

.stock-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 20px;
  padding: 15px;
}

.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stock-header h2 {
  margin: 0 0 15px 0;
  flex-grow: 1;
}

.stock-header h2.highlight {
  color: #e67e22; /* 高亮颜色 */
  font-weight: bold;
}

.remove-btn {
  background-color: #e74c3c;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.remove-btn:hover {
  background-color: #c0392b;
}

.chart-container {
  width: 100%;
  height: 400px;
}

.strategies-panel {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.strategies-panel h3 {
  margin: 0 0 15px 0;
  color: #495057;
  font-size: 16px;
  font-weight: 600;
}

.strategies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
}

.strategy-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #dee2e6;
  font-size: 14px;
}

.strategy-name {
  font-weight: 600;
  color: #495057;
  min-width: 80px;
}

.strategy-result.positive {
  color: #28a745;
  font-weight: 600;
}

.strategy-result.negative {
  color: #6c757d;
  font-weight: 600;
}

.strategy-signal {
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.signal-buy {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.signal-sell {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.signal-hold {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.signal-insufficient_data {
  background-color: #e2e3e5;
  color: #383d41;
  border: 1px solid #d1ecf1;
}

.strategy-detail {
  color: #6c757d;
  font-size: 12px;
  font-style: italic;
}

/* 可点击的策略项 */
.strategy-item.clickable {
  cursor: pointer;
  transition: background-color 0.2s;
  position: relative;
}

.strategy-item.clickable:hover {
  background-color: #f0f8ff;
}

.detail-hint {
  font-size: 12px;
  color: #888;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.strategy-item.clickable:hover .detail-hint {
  opacity: 1;
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #333;
}

.modal-body {
  padding: 20px;
}

.stock-info {
  margin-bottom: 20px;
}

.stock-info h4 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 18px;
}

.overall-score {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.score-label {
  font-weight: bold;
  color: #333;
}

.score-value {
  font-size: 24px;
  font-weight: bold;
  color: #2196F3;
}

.health-level {
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
}

.level-excellent {
  background-color: #4CAF50;
  color: white;
}

.level-good {
  background-color: #8BC34A;
  color: white;
}

.level-fair {
  background-color: #FFC107;
  color: #333;
}

.level-poor {
  background-color: #FF9800;
  color: white;
}

.level-very_poor {
  background-color: #F44336;
  color: white;
}

.scoring-details {
  margin-bottom: 20px;
}

.scoring-details h5 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 4px solid #2196F3;
}

.metric-name {
  font-weight: bold;
  color: #333;
}

.metric-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.metric-value {
  color: #2196F3;
  font-weight: bold;
}

.metric-score {
  background: #e3f2fd;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #1976d2;
}

.metric-value-extra {
  color: #666;
  font-size: 12px;
  margin-left: 5px;
}

.metric-period {
  margin-top: 4px;
  color: #888;
  font-size: 11px;
}

.scoring-criteria {
  margin-bottom: 20px;
}

.scoring-criteria h5 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.criteria-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.criteria-section {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
}

.criteria-section h6 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 14px;
  font-weight: bold;
}

.criteria-section ul {
  margin: 0;
  padding-left: 15px;
  list-style-type: disc;
}

.criteria-section li {
  margin-bottom: 5px;
  font-size: 13px;
  color: #666;
}

.health-levels {
  margin-bottom: 20px;
}

.health-levels h5 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.level-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.level-item {
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: bold;
}

.data-source {
  text-align: center;
  padding-top: 15px;
  border-top: 1px solid #eee;
  color: #888;
}

.data-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.data-advantage {
  margin-top: 8px;
}

.advantage-badge {
  background: linear-gradient(45deg, #4CAF50, #8BC34A);
  color: white;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: bold;
  display: inline-block;
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
}

/* PEG弹窗样式 */
.peg-level {
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
}

.level-very_undervalued {
  background-color: #4CAF50;
  color: white;
}

.level-undervalued {
  background-color: #8BC34A;
  color: white;
}

.level-fair {
  background-color: #FFC107;
  color: #333;
}

.level-overvalued {
  background-color: #FF9800;
  color: white;
}

.level-very_overvalued {
  background-color: #F44336;
  color: white;
}

.level-negative_growth {
  background-color: #9E9E9E;
  color: white;
}

.formula-box {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #2196F3;
  margin-bottom: 20px;
}

.formula {
  font-size: 18px;
  font-weight: bold;
  color: #333;
  margin-bottom: 8px;
  text-align: center;
}

.calculation {
  font-size: 14px;
  color: #666;
  text-align: center;
  font-family: monospace;
}

.component-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.component-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #2196F3;
}

.component-label {
  font-weight: bold;
  color: #333;
}

.component-value {
  color: #2196F3;
  font-weight: bold;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.analysis-section {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
}

.analysis-section h6 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 14px;
  font-weight: bold;
}

.analysis-section ul {
  margin: 0;
  padding-left: 15px;
  list-style-type: disc;
}

.analysis-section li {
  margin-bottom: 5px;
  font-size: 13px;
  color: #666;
}

.result-box {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #4CAF50;
}

.result-signal {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.signal-label, .reason-label {
  font-weight: bold;
  color: #333;
}

.result-reason {
  display: flex;
  align-items: center;
  gap: 10px;
}

.reason-text {
  color: #666;
  font-style: italic;
}

.metric-calculation {
  margin-top: 8px;
  padding: 8px;
  background: #f0f8ff;
  border-radius: 4px;
  border-left: 3px solid #2196F3;
}

.metric-calculation small {
  display: block;
  color: #666;
  font-size: 11px;
  line-height: 1.4;
  margin-bottom: 2px;
}
</style>