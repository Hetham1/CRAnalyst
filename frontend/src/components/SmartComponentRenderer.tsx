import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatNumber } from "@/lib/format";
import type { AgentUIComponent } from "@/types/agent";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type Props = {
  component: AgentUIComponent;
  onFollowUp: (prompt: string) => void;
};

export function SmartComponentRenderer({ component, onFollowUp }: Props) {
  switch (component.type) {
    case "text":
      return (
        <Card className="rounded-3xl border border-white/5 bg-black/40 p-4 shadow-lg">
          <p className="text-sm leading-relaxed text-white/90">{component.content}</p>
        </Card>
      );
    case "table":
      return <TableBlock data={component.data} />;
    case "chart":
      return (
        <Card className="rounded-3xl border border-white/5 bg-black/30 p-4">
          <ChartBlock data={component.data} chartType={component.chart_type} />
        </Card>
      );
    case "asset_intel": // NEW: Handle asset_intel type
      return <AssetIntelVisualization payload={component.data} />;
    case "metric_grid":
      return <MetricGrid data={component.data} />;
    case "news_list":
      return <NewsList data={component.data} />;
    case "alerts_panel":
      return <AlertsPanel data={component.data} />;
    case "portfolio":
      return <PortfolioPanel data={component.data} />;
    case "watchlist":
      return <WatchlistPanel data={component.data} />;
    case "follow_up":
      return <FollowUpPanel data={component.data} onFollowUp={onFollowUp} />;
    case "asset_overview":
      return <AssetOverviewVisualization payload={component.data} />;
    case "compare_assets":
      return <ComparisonVisualization payload={component.data} />;
    case "fundamentals_snapshot":
      return <FundamentalsVisualization payload={component.data} />;
    case "price_quotes":
      return <PriceQuotesVisualization payload={component.data} />;
    case "trending_coins":
      return <TrendingVisualization payload={component.data} />;
    case "technical_analysis":
      return <TechnicalAnalysisPanel data={component.data} />;
    case "market_pulse":
      return <MarketPulsePanel data={component.data} />;
    default:
      return (
        <Card className="rounded-3xl border border-white/10 bg-black/30 p-4 text-xs text-muted-foreground">
          <p className="font-semibold uppercase tracking-[0.4rem] text-white/70">
            {component.type}
          </p>
          <pre className="mt-2 whitespace-pre-wrap break-words">
            {JSON.stringify(component.data ?? component.content, null, 2)}
          </pre>
        </Card>
      );
  }
}

function TableBlock({ data }: { data?: Record<string, any> }) {
  const headers: string[] = data?.headers ?? [];
  const rows: any[] = data?.rows ?? [];
  if (!headers.length || !rows.length) return null;
  return (
    <div className="overflow-x-auto rounded-3xl border border-white/10 bg-black/30">
      <table className="min-w-full divide-y divide-white/5 text-sm">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header} className="px-4 py-3 text-left text-xs uppercase tracking-[0.3rem] text-muted-foreground">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-white/80">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((header) => (
                <td key={header} className="px-4 py-3">
                  {row[header]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricGrid({ data }: { data?: Record<string, any> }) {
  const metrics: Array<{ label: string; value: string; accent?: string }> = data?.metrics ?? [];
  if (!metrics.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3"
        >
          <p className="text-[10px] uppercase tracking-[0.4rem] text-muted-foreground">
            {metric.label}
          </p>
          <p className="text-xl font-semibold text-white">{metric.value}</p>
          {metric.accent ? (
            <p className="text-xs text-muted-foreground">{metric.accent}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ChartBlock({
  data,
  chartType,
}: {
  data?: Record<string, any>;
  chartType?: string;
}) {
  const dataset = (data?.series ?? []).map((point: any) => {
    if (point.label) return point;
    if (point.timestamp) return { label: point.timestamp, ...point };
    return point;
  });
  if (!dataset.length) return null;
  if (chartType === "donut") {
    const segments = data?.segments ?? dataset;
    const colors = ["#a855f7", "#0ea5e9", "#22c55e", "#f97316", "#f43f5e", "#6366f1"];
    return (
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <ResponsiveContainer width="60%" height={240}>
          <PieChart>
            <Pie
              data={segments}
              dataKey="value"
              nameKey="label"
              innerRadius={60}
              outerRadius={100}
            >
              {segments.map((_: any, index: number) => (
                <Cell
                  key={index}
                  fill={colors[index % colors.length]}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "rgba(9,9,11,0.9)",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-2 text-sm text-muted-foreground">
          {segments.map((segment: any, index: number) => (
            <div key={segment.label} className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: colors[index % colors.length] }}
              />
              <span className="text-white/80">{segment.label}</span>
              <span>{formatNumber(segment.value, { notation: "compact" })}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (chartType === "bar") {
    const keys = data?.keys ?? Object.keys(dataset[0] ?? {}).filter((key) => key !== "label");
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={dataset}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
          <XAxis dataKey="label" hide={dataset.length > 20} />
          <YAxis />
          <Tooltip
            contentStyle={{
              background: "rgba(9,9,11,0.9)",
              borderRadius: "12px",
              border: "1px solid rgba(255,255,255,0.1)",
            }}
          />
          <Legend />
          {keys.map((key: string, idx: number) => (
            <Bar key={key} dataKey={key} fill={BAR_COLORS[idx % BAR_COLORS.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={dataset}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
        <XAxis dataKey="label" hide={dataset.length > 30} />
        <YAxis />
        <Tooltip
          contentStyle={{
            background: "rgba(9,9,11,0.9)",
            borderRadius: "12px",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        />
        <Legend />
        {extractLineKeys(dataset).map((key, idx) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={LINE_COLORS[idx % LINE_COLORS.length]}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function NewsList({ data }: { data?: Record<string, any> }) {
  const items: Array<{ title: string; source: string; url: string; published_at?: string }> =
    data?.items ?? [];
  if (!items.length) return null;
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.title}
          className="rounded-3xl border border-white/5 bg-black/30 p-4 text-sm"
        >
          <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
            {item.source}
          </p>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 block text-base font-semibold text-white hover:text-primary"
          >
            {item.title}
          </a>
          {item.published_at ? (
            <p className="text-xs text-muted-foreground">
              {new Date(item.published_at).toLocaleString()}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function AlertsPanel({ data }: { data?: Record<string, any> }) {
  const alerts: any[] = data?.alerts ?? [];
  if (!alerts.length) return null;
  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className="rounded-3xl border border-white/10 bg-black/30 px-4 py-3 text-sm"
        >
          <div className="flex items-center justify-between">
            <p className="font-semibold text-white">{alert.description ?? "Alert"}</p>
            <span
              className={`rounded-full px-3 py-1 text-xs ${
                alert.status === "triggered"
                  ? "bg-emerald-400/20 text-emerald-300"
                  : "bg-slate-500/20 text-slate-200"
              }`}
            >
              {alert.status}
            </span>
          </div>
          {alert.context?.matches ? (
            <p className="text-xs text-muted-foreground">
              {alert.context.matches.map((match: any) => `${match.asset}: ${match.change_pct?.toFixed(2)}%`).join(" • ")}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function PortfolioPanel({ data }: { data?: Record<string, any> }) {
  if (!data) return null;
  const positions = data.positions ?? [];
  const totals = data.totals ?? {};
  const breakdown = data.breakdown ?? [];
  return (
    <div className="space-y-4 rounded-3xl border border-white/5 bg-black/30 p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Invested" value={`$${formatNumber(totals.invested, { notation: "compact" })}`} />
        <MetricCard label="Value" value={`$${formatNumber(totals.value, { notation: "compact" })}`} />
        <MetricCard
          label="P/L"
          value={`${totals.pnl_abs >= 0 ? "+" : "-"}$${formatNumber(Math.abs(totals.pnl_abs), {
            notation: "compact",
          })}`}
        />
        <MetricCard
          label="P/L %"
          value={`${totals.pnl_pct?.toFixed?.(2) ?? formatNumber(totals.pnl_pct)}%`}
        />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">Allocation</p>
          <ChartBlock
            data={{ segments: breakdown.map((row: any) => ({ label: row.asset?.toUpperCase(), value: row.value })) }}
            chartType="donut"
          />
        </div>
        <ScrollArea className="max-h-72 rounded-3xl border border-white/5 bg-black/20">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
                <th className="px-4 py-3 text-left">Asset</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-right">Value</th>
                <th className="px-4 py-3 text-right">P/L %</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos: any) => (
                <tr key={pos.id} className="text-white/80">
                  <td className="px-4 py-3 uppercase">{pos.asset}</td>
                  <td className="px-4 py-3 text-right">{pos.amount}</td>
                  <td className="px-4 py-3 text-right">${formatNumber(pos.current_value)}</td>
                  <td
                    className={`px-4 py-3 text-right ${
                      (pos.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {pos.pnl_pct?.toFixed?.(2) ?? pos.pnl_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </div>
    </div>
  );
}

function WatchlistPanel({ data }: { data?: Record<string, any> }) {
  const assets: string[] = data?.watchlist ?? [];
  if (!assets.length) return null;
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">Watchlist</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {assets.map((asset) => (
          <span
            key={asset}
            className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs uppercase text-primary"
          >
            {asset.toUpperCase()}
          </span>
        ))}
      </div>
    </div>
  );
}

function FollowUpPanel({
  data,
  onFollowUp,
}: {
  data?: Record<string, any>;
  onFollowUp: (prompt: string) => void;
}) {
  const suggestions: string[] = data?.suggestions ?? [];
  if (!suggestions.length) return null;
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-4">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">Next Steps</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
          <Button key={suggestion} variant="secondary" size="sm" onClick={() => onFollowUp(suggestion)}>
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3 text-sm">
      <p className="text-[10px] uppercase tracking-[0.4rem] text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function MarketPulsePanel({ data }: { data?: Record<string, any> }) {
  if (!data) return null;
  return (
    <div className="space-y-4 rounded-3xl border border-white/5 bg-black/25 p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Market Cap"
          value={`$${formatNumber(data.global?.market_cap, { notation: "compact" })}`}
        />
        <MetricCard
          label="24h Change"
          value={`${formatNumber(data.global?.market_cap_change_24h_pct)}%`}
        />
        <MetricCard label="BTC Dominance" value={`${formatNumber(data.global?.btc_dominance)}%`} />
        <MetricCard label="Fear & Greed" value={`${data.sentiment?.fear_greed?.value ?? 50}`} />
      </div>
      <ChartBlock
        data={{
          series: (data.categories ?? []).map((cat: any) => ({
            label: cat.category,
            Value: Number(cat.avg_change ?? 0),
          })),
          keys: ["Value"],
        }}
        chartType="bar"
      />
      <NewsList data={{ items: data.news }} />
    </div>
  );
}

function TechnicalAnalysisPanel({ data }: { data?: Record<string, any> }) {
  if (!data) return null;
  const title = `${data.asset?.toUpperCase()} ${data.indicator} (${data.timeframe})`;
  const priceSeries = (data.series ?? []).map((point: any) => ({
    label: new Date(point.timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
    }),
    price: point.close,
  }));
  return (
    <div className="space-y-3 rounded-3xl border border-white/5 bg-black/30 p-5">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">{title}</p>
      <ChartBlock data={{ series: priceSeries }} chartType="line" />
      <div className="rounded-2xl border border-white/5 bg-black/20 p-4 text-sm text-white/80">
        <p>
          Signal:{" "}
          <span className="font-semibold text-primary">
            {data.value} ({data.state})
          </span>
        </p>
        <p className="text-muted-foreground">{data.interpretation}</p>
      </div>
    </div>
  );
}

const LINE_COLORS = ["#a855f7", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#6366f1"];
const BAR_COLORS = ["#a855f7", "#0ea5e9", "#22c55e", "#f97316", "#f43f5e", "#6366f1"];

function extractLineKeys(dataset: any[]): string[] {
  if (!dataset.length) return [];
  const baseKeys = Object.keys(dataset[0]).filter((key) => key !== "label");
  if (baseKeys.length) return baseKeys;
  return ["value"];
}

// NEW: Price structure chart rendered as an area chart for readability
function CandlestickChartBlock({ data }: { data?: Record<string, any> }) {
  const series = (data?.series ?? [])
    .map((point: any) => ({
      timestamp: point.timestamp,
      close: Number(point.close ?? point.value ?? point.price ?? null),
    }))
    .filter(
      (point) =>
        point.timestamp &&
        Number.isFinite(point.close) &&
        !Number.isNaN(point.close)
    )
    .sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

  if (!series.length) return null;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={series}>
        <defs>
          <linearGradient id="price-structure" x1="0" x2="0" y1="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(timestamp) =>
            new Date(timestamp).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })
          }
          minTickGap={30}
        />
        <YAxis domain={["dataMin", "dataMax"]} />
        <Tooltip
          contentStyle={{
            background: "rgba(9,9,11,0.9)",
            borderRadius: "12px",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
          formatter={(value: number) => `$${formatNumber(value)}`}
          labelFormatter={(label: number) =>
            new Date(label).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })
          }
        />
        <Area
          type="monotone"
          dataKey="close"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          fill="url(#price-structure)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Asset Intel Visualization Component
function AssetIntelVisualization({ payload }: { payload: any }) {
  const [resolvedPayload, setResolvedPayload] = useState<any>(payload ?? null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  useEffect(() => {
    setResolvedPayload(payload ?? null);
    setFetchError(null);
  }, [payload]);

  const asset = useMemo(() => {
    const candidates = [
      payload?.asset,
      payload?.overview?.asset,
      payload?.overview?.symbol,
      payload?.content,
    ];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim()) {
        return candidate.trim().toLowerCase();
      }
    }
    return undefined;
  }, [payload]);

  const alreadyHydrated = Boolean(payload?._hydrated);
  const needsOverview = !payload?.overview || typeof payload?.overview?.price !== "number";
  const needsNews = !Array.isArray(payload?.news) || payload.news.length === 0;
  const needsOnchain = !payload?.onchain;
  const shouldHydrateClientSide = Boolean(
    asset && !alreadyHydrated && (needsOverview || needsNews || needsOnchain)
  );

  useEffect(() => {
    let cancelled = false;
    if (!shouldHydrateClientSide || !asset) {
      return;
    }
    (async () => {
      try {
        const [overview, news, onchain] = await Promise.all([
          needsOverview
            ? fetch(`${API_BASE}/api/market/overview/${asset}`).then((res) =>
                res.ok ? res.json() : Promise.reject(new Error("Market overview unavailable."))
              )
            : null,
          needsNews
            ? fetch(`${API_BASE}/api/market/news/${asset}`).then((res) =>
                res.ok ? res.json() : Promise.reject(new Error("News feed unavailable."))
              )
            : null,
          needsOnchain
            ? fetch(`${API_BASE}/api/market/onchain/${asset}`).then((res) =>
                res.ok ? res.json() : Promise.reject(new Error("On-chain feed unavailable."))
              )
            : null,
        ]);
        if (cancelled) return;
        setResolvedPayload((prev) => {
          const base = { ...(prev ?? {}), ...(payload ?? {}), asset };
          if (overview) {
            base.overview = overview;
            if (!base.series && overview.ohlc_series) {
              base.series = overview.ohlc_series;
            }
          }
          if (news) {
            base.news = news.news ?? [];
            base.sentiment = news.sentiment ?? base.sentiment;
          }
          if (onchain) {
            base.onchain = onchain;
          }
          base._hydrated = true;
          return base;
        });
        setFetchError(null);
      } catch (error) {
        console.error("Asset intel hydration failed", error);
        if (!cancelled) {
          setFetchError(
            error instanceof Error ? error.message : "Unable to refresh market data."
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [asset, payload, shouldHydrateClientSide, needsOverview, needsNews, needsOnchain]);

  const effectivePayload = resolvedPayload ?? payload;
  if (!effectivePayload) return null;

  const overview = effectivePayload.overview ?? {};
  const newsItems = effectivePayload.news ?? [];
  const sentiment = effectivePayload.sentiment ?? {};
  const onchain = effectivePayload.onchain ?? {};
  const backendErrors: string[] = Array.isArray(payload?.errors) ? payload.errors : [];
  const combinedErrors = [
    ...backendErrors.filter(Boolean),
    ...(fetchError ? [fetchError] : []),
  ];
  const currency = (overview.currency ?? "usd").toUpperCase();
  const price = typeof overview.price === "number" ? overview.price : null;
  const change = typeof overview.change_24h === "number" ? overview.change_24h : null;
  const sparkline: number[] = Array.isArray(overview.sparkline) ? overview.sparkline : [];
  const sparklineData = sparkline.map((value, index) => ({ label: index, value }));
  const ohlcSeries = effectivePayload.series ?? overview.ohlc_series ?? [];

  const formatCurrency = (value?: number | null) => {
    if (value === undefined || value === null) return "—";
    const formatted = formatNumber(value, { notation: "compact" });
    return currency === "USD" ? `$${formatted}` : `${formatted} ${currency}`;
  };

  const metrics = [
    { label: "Market Cap", value: formatCurrency(overview.market_cap) },
    { label: "24h Volume", value: formatCurrency(overview.volume_24h) },
    {
      label: "Circulating",
      value: overview.circulating_supply ? `${formatNumber(overview.circulating_supply, { maximumFractionDigits: 0 })}` : "—",
    },
    {
      label: "Rank",
      value: overview.market_cap_rank ? `#${overview.market_cap_rank}` : "—",
    },
  ];

  const keywords: string[] = sentiment.keywords ?? [];
  const whale = onchain.whale_activity ?? {};
  const growth = onchain.network_growth ?? {};

  return (
    <div className="space-y-4">
      {combinedErrors.length > 0 && (
        <div className="rounded-2xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-100">
          <p className="font-semibold uppercase tracking-[0.2rem] text-xs text-yellow-200">Data Notice</p>
          <ul className="mt-1 space-y-1">
            {combinedErrors.map((message, index) => (
              <li key={`${message}-${index}`}>{message}</li>
            ))}
          </ul>
        </div>
      )}
      <Card className="space-y-4 rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
              {overview.name ?? effectivePayload.asset?.toUpperCase() ?? "Asset"}
            </p>
            <p className="text-3xl font-semibold text-white">
              {price === null ? "—" : formatCurrency(price)}
            </p>
            {change !== null && (
              <p className={`text-sm ${change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatNumber(change)}% 24h
              </p>
            )}
          </div>
          <div className="grid min-w-[220px] gap-3 sm:grid-cols-2">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-2xl border border-white/10 bg-black/30 px-4 py-3">
                <p className="text-[10px] uppercase tracking-[0.4rem] text-muted-foreground">{metric.label}</p>
                <p className="text-sm font-semibold text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
        {sparklineData.length > 0 && (
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparklineData}>
                <defs>
                  <linearGradient id={`spark-${effectivePayload.asset ?? "asset"}`} x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.6} />
                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                <XAxis dataKey="label" hide />
                <YAxis hide domain={["dataMin", "dataMax"]} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(9,9,11,0.9)",
                    borderRadius: "12px",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  fill={`url(#spark-${effectivePayload.asset ?? "asset"})`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {ohlcSeries.length > 0 && (
          <Card className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
            <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">Price Structure</p>
            <CandlestickChartBlock data={{ series: ohlcSeries }} />
          </Card>
        )}
        <div className="space-y-4">
          {(sentiment.label || sentiment.score !== undefined) && (
            <Card className="rounded-3xl border border-white/5 bg-black/25 p-5">
              <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">News Sentiment</p>
              <p className="mt-2 text-2xl font-semibold text-white capitalize">
                {sentiment.label ?? "neutral"}{" "}
                {sentiment.score !== undefined ? (
                  <span className="text-base text-muted-foreground">({formatNumber(sentiment.score)})</span>
                ) : null}
              </p>
              {keywords.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {keywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/80"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              )}
              {sentiment.sample_size && (
                <p className="mt-3 text-xs text-muted-foreground">{sentiment.sample_size} articles scanned</p>
              )}
            </Card>
          )}

          {(whale.state || growth.state) && (
            <Card className="rounded-3xl border border-white/5 bg-black/25 p-5">
              <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">On-Chain Pulse</p>
              {whale.state && (
                <div className="mt-3">
                  <p className="text-sm text-muted-foreground">Whales</p>
                  <p className="text-lg font-semibold text-white">{whale.state}</p>
                  {whale.largest_transaction_usd && (
                    <p className="text-xs text-muted-foreground">
                      Largest tx: {formatCurrency(whale.largest_transaction_usd)}
                    </p>
                  )}
                </div>
              )}
              {growth.state && (
                <div className="mt-4">
                  <p className="text-sm text-muted-foreground">Network Growth</p>
                  <p className="text-lg font-semibold text-white">{growth.state}</p>
                  {growth.heat_pct !== undefined && (
                    <p className="text-xs text-muted-foreground">{formatNumber(growth.heat_pct)}% mempool heat</p>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>
      </div>

      {newsItems.length > 0 && (
        <Card className="rounded-3xl border border-white/5 bg-black/25 p-5">
          <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">Top Headlines</p>
          <div className="mt-3">
            <NewsList data={{ items: newsItems }} />
          </div>
        </Card>
      )}
    </div>
  );
}

// Legacy visualization blocks reused for streaming tool payloads
function AssetOverviewVisualization({ payload }: { payload: any }) {
  if (!payload) return null;
  const prices =
    payload.series?.prices ?? payload.fundamentals?.series?.prices ?? [];
  const volumes =
    payload.series?.volumes ?? payload.fundamentals?.series?.volumes ?? [];

  const priceData = prices.map((point: any) => ({
    label: new Date(point.timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
    value: point.value,
  }));

  const volumeData = volumes.map((point: any) => ({
    label: new Date(point.timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
    }),
    value: point.value,
  }));

  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
      <div className="mb-4 flex items-center gap-3">
        <Sparkles className="h-5 w-5 text-primary" />
        <div>
          <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
            {payload.name} Overview
          </p>
          <p className="text-lg font-semibold">
            ${formatNumber(payload.price)}{" "}
            <span
              className={
                (payload.change_24h ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
              }
            >
              {formatNumber(payload.change_24h)}%
            </span>
          </p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Market Cap" value={`$${formatNumber(payload.market_cap, { notation: "compact" })}`} />
        <MetricCard label="24h Volume" value={`$${formatNumber(payload.volume_24h, { notation: "compact" })}`} />
        <MetricCard label="Supply" value={formatNumber(payload.circulating_supply, { maximumFractionDigits: 0 })} />
        <MetricCard label="Rank" value={`#${payload.market_cap_rank ?? "—"}`} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="7d Price" data={priceData} color="hsl(var(--primary))" />
        <ChartCard title="7d Volume" data={volumeData} color="hsl(var(--accent))" />
      </div>
    </div>
  );
}

function ComparisonVisualization({ payload }: { payload: any }) {
  const data = (payload?.comparisons ?? []).map((item: any) => ({
    name: item.target.toUpperCase(),
    Base: item.base_price ?? 0,
    Target: item.target_price ?? 0,
    Spread: item.spread ?? 0,
  }));
  if (!data.length) return null;
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
        Comparison vs {payload.base?.toUpperCase()}
      </p>
      <div className="mt-4 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip
              contentStyle={{
                background: "rgba(9,9,11,0.9)",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
            <Legend />
            <Bar dataKey="Base" fill="hsl(var(--muted-foreground))" />
            <Bar dataKey="Target" fill="hsl(var(--primary))" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function FundamentalsVisualization({ payload }: { payload: any }) {
  const series = payload?.series?.prices ?? [];
  const data = series.map((point: any) => ({
    label: new Date(point.timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
    }),
    value: point.value,
  }));
  if (!data.length) return null;
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
        Weekly Fundamentals Snapshot
      </p>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip
              contentStyle={{
                background: "rgba(9,9,11,0.9)",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
            <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PriceQuotesVisualization({ payload }: { payload: any }) {
  const quotes = payload?.quotes ?? [];
  if (!quotes.length) return null;
  const data = quotes.map((quote: any) => ({
    name: quote.asset.toUpperCase(),
    price: quote.price,
  }));
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
        Snapshot Quotes ({payload.currency?.toUpperCase()})
      </p>
      <div className="mt-4 h-60">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip
              contentStyle={{
                background: "rgba(9,9,11,0.9)",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
            <Bar dataKey="price" fill="hsl(var(--accent))" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function TrendingVisualization({ payload }: { payload: any }) {
  const trending = payload?.trending ?? [];
  if (!trending.length) return null;
  const data = trending.map((coin: any) => ({
    name: coin.symbol,
    score: coin.score,
  }));
  return (
    <div className="rounded-3xl border border-white/5 bg-black/30 p-5 shadow-xl">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
        Trending Momentum
      </p>
      <div className="mt-4 h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip
              contentStyle={{
                background: "rgba(9,9,11,0.9)",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ChartCard({
  title,
  data,
  color,
}: {
  title: string;
  data: { label: string; value: number }[];
  color: string;
}) {
  return (
    <div className="h-64 rounded-3xl border border-white/5 bg-black/20 p-4">
      <p className="text-xs uppercase tracking-[0.4rem] text-muted-foreground">
        {title}
      </p>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={title} x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.8} />
              <stop offset="95%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
          <XAxis dataKey="label" hide />
          <Tooltip
            contentStyle={{
              background: "rgba(9,9,11,0.9)",
              borderRadius: "12px",
              border: "1px solid rgba(255,255,255,0.1)",
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            fill={`url(#${title})`}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

