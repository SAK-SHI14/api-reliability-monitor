import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, Database, TrendingUp, AlertCircle, ShieldCheck,
  Globe, Zap, Cpu, RefreshCw, Layers
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import './App.css';

const API_URL = 'http://localhost:8000/api';

// Types
interface ApiMetric {
  id: number;
  timestamp: number;
  api_name: string;
  url: string;
  latency_ms: number;
  status_code: number;
  is_success: number;
}

interface PipelineEvent {
  id: number;
  timestamp: number;
  event_type: string;
  stage: string;
  metrics: any;
}

interface LlmTrace {
  trace_id: string;
  prompt_text: string;
  model: string;
  provider: string;
  response_text: string;
  total_tokens: number;
  total_latency_ms: number;
  request_ts: number;
  estimated_cost_usd: number;
  tokens_per_second: number;
  ttft_ms: number;
}

function StatCard({ title, value, icon: Icon, trend, classNameGlow, suffix = '', sparklineData }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass-panel stat-card"
    >
      <div className="stat-header">
        <div>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</h3>
          <div className="metric-value" style={{ marginTop: '0.5rem' }}>
            {value}<span style={{ fontSize: '1rem', color: 'var(--text-tertiary)', marginLeft: '0.25rem' }}>{suffix}</span>
          </div>
        </div>
        <div className={`stat-icon ${classNameGlow}`}>
          <Icon size={24} />
        </div>
      </div>
      {(trend !== undefined || sparklineData) && (
        <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {trend !== undefined && (
            <div className={trend >= 0 ? "trend-up" : "trend-down"}>
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}% <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>vs last hr</span>
            </div>
          )}
          {sparklineData && (
            <div style={{ width: '80px', height: '30px' }}>
               <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparklineData}>
                    <defs>
                      <linearGradient id={`grad-${title}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={trend >= 0 ? "var(--accent-emerald)" : "var(--accent-rose)"} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={trend >= 0 ? "var(--accent-emerald)" : "var(--accent-rose)"} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="value" stroke={trend >= 0 ? "var(--accent-emerald)" : "var(--accent-rose)"} fill={`url(#grad-${title})`} strokeWidth={2} />
                  </AreaChart>
               </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}

function App() {
  const [apiMetrics, setApiMetrics] = useState<ApiMetric[]>([]);
  const [pipelineEvents, setPipelineEvents] = useState<PipelineEvent[]>([]);
  const [llmTraces, setLlmTraces] = useState<LlmTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const fetchData = async () => {
    try {
      const [apiRes, pipeRes, llmRes] = await Promise.all([
        axios.get(`${API_URL}/api-metrics`),
        axios.get(`${API_URL}/pipeline-events`),
        axios.get(`${API_URL}/llm-traces`)
      ]);
      // Sort to order by time ascending for charts
      setApiMetrics(apiRes.data.sort((a: any, b: any) => a.timestamp - b.timestamp));
      setPipelineEvents(pipeRes.data);
      setLlmTraces(llmRes.data);
      setLastUpdated(new Date());
    } catch (e) {
      console.error("Failed to fetch data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  // Compute aggregate stats
  const aggregateStats = useMemo(() => {
    const defaultStats = { avgLatency: 0, uptime: 100, llmLatency: 0, totalTraces: 0, tokenSpeed: 0 };
    if (!apiMetrics.length || !llmTraces.length) return defaultStats;

    const recentApi = apiMetrics.slice(-50);
    const avgLat = recentApi.reduce((sum, m) => sum + m.latency_ms, 0) / recentApi.length;
    const successes = recentApi.filter(m => m.is_success).length;
    const uptime = (successes / recentApi.length) * 100;

    const avgLlmLat = llmTraces.reduce((sum, t) => sum + t.total_latency_ms, 0) / llmTraces.length;
    const avgTokSpeed = llmTraces.reduce((sum, t) => sum + t.tokens_per_second, 0) / llmTraces.length;

    return {
      avgLatency: avgLat.toFixed(0),
      uptime: uptime.toFixed(2),
      llmLatency: avgLlmLat.toFixed(0),
      totalTraces: llmTraces.length,
      tokenSpeed: avgTokSpeed.toFixed(1)
    };
  }, [apiMetrics, llmTraces]);



  // Group by time for aggregated view (approx)
  // Here we just plot directly since it's an overview
  const latencyChartData = apiMetrics.slice(-40).map(m => ({
    time: new Date(m.timestamp * 1000).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }),
    [m.api_name]: m.latency_ms,
    total: m.latency_ms
  }));

  const sparkData = latencyChartData.map(d => ({ value: d.total }));

  if (loading && apiMetrics.length === 0) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
          <RefreshCw size={48} color="var(--accent-blue)" />
        </motion.div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">
            <Layers size={22} />
          </div>
          <div>
            <h1 className="title-gradient" style={{ fontSize: '1.25rem', margin: 0 }}>OmniWatch Observer</h1>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Unified Telemetry Platform</div>
          </div>
        </div>
        <div className="header-status">
          <div className="status-indicator status-healthy"></div>
          System Operational
          <div style={{ width: '1px', height: '16px', background: 'var(--glass-border)', margin: '0 0.5rem' }}></div>
          <span style={{ color: 'var(--text-secondary)' }}>
            Updated: {lastUpdated.toLocaleTimeString()}
          </span>
        </div>
      </header>

      {/* DASHBOARD GRID */}
      <main className="dashboard-grid">
        
        {/* ROW 1: STATS */}
        <div style={{ gridColumn: 'span 12', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
          <StatCard 
            title="API Global Uptime" 
            value={aggregateStats.uptime} 
            suffix="%" 
            icon={ShieldCheck} 
            classNameGlow="emerald-glow"
            trend={0.02}
            sparklineData={sparkData}
          />
          <StatCard 
            title="Avg API Latency" 
            value={aggregateStats.avgLatency} 
            suffix="ms" 
            icon={Activity} 
            classNameGlow="blue-glow"
            trend={-12}
            sparklineData={sparkData}
          />
          <StatCard 
            title="LLM Avg Latency" 
            value={aggregateStats.llmLatency} 
            suffix="ms" 
            icon={Cpu} 
            classNameGlow="purple-glow"
            trend={4.5}
          />
          <StatCard 
            title="Token Velocity" 
            value={aggregateStats.tokenSpeed} 
            suffix="tok/s" 
            icon={Zap} 
            classNameGlow="amber-glow"
            trend={1.2}
          />
        </div>

        {/* ROW 2: API LATENCY CHART & PIPELINE HEALTH */}
        <div style={{ gridColumn: 'span 8' }} className="glass-panel chart-container">
          <div className="chart-header">
            <h2 className="chart-title"><Globe size={20} style={{ display: 'inline', marginRight: '0.5rem', color: 'var(--accent-blue)' }}/> Network API Telemetry</h2>
            <div className="badge badge-info">Real-time (Last 40 pings)</div>
          </div>
          <div style={{ height: '350px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={latencyChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorLat" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={12} tickMargin={10} />
                <YAxis stroke="var(--text-tertiary)" fontSize={12} tickFormatter={(val: any) => `${val}ms`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(15, 20, 35, 0.9)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="total" stroke="var(--accent-blue)" fillOpacity={1} fill="url(#colorLat)" strokeWidth={3} activeDot={{ r: 6, fill: '#fff', stroke: 'var(--accent-blue)' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ gridColumn: 'span 4' }} className="glass-panel chart-container">
          <div className="chart-header">
            <h2 className="chart-title"><Database size={20} style={{ display: 'inline', marginRight: '0.5rem', color: 'var(--accent-emerald)' }}/> Pipeline Health</h2>
          </div>
          <div className="table-wrapper" style={{ maxHeight: '350px', overflowY: 'auto' }}>
            <table className="modern-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Status</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {pipelineEvents.slice(0, 8).map((evt) => (
                    <motion.tr 
                      key={evt.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                    >
                      <td style={{ fontWeight: 500 }}>{evt.stage}</td>
                      <td>
                        <span className={`badge ${evt.event_type === 'success' ? 'badge-success' : evt.event_type === 'error' ? 'badge-error' : 'badge-warning'}`}>
                          {evt.event_type}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-tertiary)' }}>
                        {new Date(evt.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute:'2-digit', second:'2-digit' })}
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </div>

        {/* ROW 3: LLM OBSERVABILITY TRACES */}
        <div style={{ gridColumn: 'span 12' }} className="glass-panel chart-container">
          <div className="chart-header">
            <h2 className="chart-title"><Cpu size={20} style={{ display: 'inline', marginRight: '0.5rem', color: 'var(--accent-purple)' }}/> LLM Observability & Traces</h2>
            <div className="badge badge-warning">Drift Detected</div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1rem' }}>
            {llmTraces.slice(0, 6).map((trace) => (
              <motion.div 
                key={trace.trace_id} 
                className="trace-card glass-panel"
                whileHover={{ scale: 1.01 }}
              >
                <div className="trace-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div className="badge badge-info">{trace.model}</div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                      {trace.provider.toUpperCase()} • {new Date(trace.request_ts * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                  <div>
                    {trace.total_latency_ms > 800 ? (
                      <AlertCircle size={16} color="var(--accent-rose)" />
                    ) : (
                      <ShieldCheck size={16} color="var(--accent-emerald)" />
                    )}
                  </div>
                </div>
                
                <div className="trace-prompt">
                  <strong>P:</strong> {trace.prompt_text.length > 50 ? trace.prompt_text.substring(0, 50) + '...' : trace.prompt_text}
                  <br/>
                  <strong style={{ color: 'var(--text-primary)'}}>R:</strong> {trace.response_text.length > 70 ? trace.response_text.substring(0, 70) + '...' : trace.response_text}
                </div>
                
                <div className="metrics-row">
                  <div className="metric-item">
                    <Activity size={14} color="var(--accent-purple)" />
                    {trace.total_latency_ms}ms (TTFT {trace.ttft_ms}ms)
                  </div>
                  <div className="metric-item">
                    <Layers size={14} color="var(--accent-amber)" />
                    {trace.total_tokens} tokens
                  </div>
                  <div className="metric-item">
                    <TrendingUp size={14} color="var(--accent-emerald)" />
                    {trace.tokens_per_second.toFixed(1)} t/s
                  </div>
                  <div className="metric-item">
                    <span style={{ color: 'var(--accent-rose)' }}>$</span>
                    {trace.estimated_cost_usd.toFixed(4)}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
}

export default App;
