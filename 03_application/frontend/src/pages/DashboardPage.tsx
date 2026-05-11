import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../api/client';
import FieldMapManager from '../components/FieldMapManager';
import { useAuth } from '../context/AuthContext';
import { ACCEPTED_UPLOAD_EXTENSIONS, validateUploadInput } from '../utils/uploadValidation';
import type {
  AnalyticsOverview,
  EnvironmentOverview,
  ExploratoryReportResponse,
  FieldMapSummary,
  FieldTimeseries,
  FieldMapDetail,
  InsightDashboard,
  ModelStats,
  TrapPoint,
  UploadBatchResponse,
  UploadDetail,
  UploadSummary,
} from '../types/api';

const BLUE_SCALE = {
  b100: '#dbeafe',
  b300: '#93c5fd',
  b400: '#60a5fa',
  b500: '#3b82f6',
  b600: '#2563eb',
  b700: '#1d4ed8',
  b800: '#1e40af',
};

function SimpleBarChart({
  title,
  labels,
  values,
  xLabel,
  yLabel,
  color = BLUE_SCALE.b600,
}: {
  title: string;
  labels: string[];
  values: number[];
  xLabel: string;
  yLabel: string;
  color?: string;
}) {
  const width = 720;
  const height = 280;
  const margin = { top: 16, right: 16, bottom: 52, left: 56 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const rawMin = values.length > 0 ? Math.min(...values) : 0;
  const rawMax = values.length > 0 ? Math.max(...values) : 1;
  const span = Math.max(rawMax - rawMin, 1e-6);
  const pad = span * 0.08;
  let domainMin = rawMin - pad;
  let domainMax = rawMax + pad;
  if (domainMin === domainMax) {
    domainMin -= 1;
    domainMax += 1;
  }
  const includesZero = domainMin <= 0 && domainMax >= 0;
  const yFor = (v: number) => margin.top + ((domainMax - v) / (domainMax - domainMin)) * innerHeight;
  const baselineY = includesZero ? yFor(0) : yFor(domainMin);
  const gap = 6;
  const barWidth = Math.max(6, innerWidth / Math.max(values.length, 1) - gap);
  const yTicks = 5;
  const tickValues = Array.from({ length: yTicks + 1 }, (_, i) => domainMin + ((domainMax - domainMin) * i) / yTicks).reverse();
  const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1));
  const gradId = `barFillBlue-${title.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div className="card">
      <h3>{title}</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="line-chart">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BLUE_SCALE.b400} />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        {tickValues.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={`tick-${tick}`}>
              <line x1={margin.left} y1={y} x2={width - margin.right} y2={y} stroke="#dbeafe" strokeWidth="1" />
              <text x={margin.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#475569">
                {fmt(tick)}
              </text>
            </g>
          );
        })}
        <line x1={margin.left} y1={baselineY} x2={width - margin.right} y2={baselineY} stroke="#1e3a8a" strokeWidth="1.2" />
        <line x1={margin.left} y1={margin.top} x2={margin.left} y2={height - margin.bottom} stroke="#1e3a8a" strokeWidth="1.2" />
        {values.map((value, idx) => {
          const x = margin.left + idx * (barWidth + gap) + gap / 2;
          const y = yFor(value);
          const yNeg = baselineY;
          const barY = Math.min(y, yNeg);
          const barH = Math.max(2, Math.abs(y - yNeg));
          return (
            <g key={`${labels[idx]}-${idx}`}>
              <rect x={x} y={barY} width={barWidth} height={barH} fill={`url(#${gradId})`} rx="2">
                <title>{`${labels[idx]}: ${value.toFixed(2)}`}</title>
              </rect>
              <text x={x + barWidth / 2} y={height - margin.bottom + 14} textAnchor="middle" fontSize="10" fill="#64748b">
                {labels[idx]}
              </text>
            </g>
          );
        })}
        <text x={margin.left + innerWidth / 2} y={height - 10} textAnchor="middle" fontSize="12" fill="#334155">
          {xLabel}
        </text>
        <text
          x={14}
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${margin.top + innerHeight / 2})`}
          fontSize="12"
          fill="#334155"
        >
          {yLabel}
        </text>
      </svg>
    </div>
  );
}

function SimpleLineChart({
  title,
  labels,
  values,
  xLabel,
  yLabel,
  stroke = BLUE_SCALE.b600,
}: {
  title: string;
  labels: string[];
  values: number[];
  xLabel: string;
  yLabel: string;
  stroke?: string;
}) {
  const width = 720;
  const height = 280;
  const margin = { top: 16, right: 16, bottom: 52, left: 56 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const rawMin = values.length > 0 ? Math.min(...values) : 0;
  const rawMax = values.length > 0 ? Math.max(...values) : 1;
  const span = Math.max(rawMax - rawMin, 1e-6);
  const pad = span * 0.08;
  let domainMin = rawMin - pad;
  let domainMax = rawMax + pad;
  if (domainMin === domainMax) {
    domainMin -= 1;
    domainMax += 1;
  }
  const xStep = values.length > 1 ? innerWidth / (values.length - 1) : 0;
  const xFor = (i: number) => margin.left + i * xStep;
  const yFor = (v: number) => margin.top + ((domainMax - v) / (domainMax - domainMin)) * innerHeight;
  const points = values.map((v, i) => `${xFor(i)},${yFor(v)}`).join(' ');
  const yTicks = 5;
  const tickValues = Array.from({ length: yTicks + 1 }, (_, i) => domainMin + ((domainMax - domainMin) * i) / yTicks).reverse();
  const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1));
  const areaId = `lineAreaBlue-${title.replace(/[^a-zA-Z0-9]/g, '')}`;
  return (
    <div className="card">
      <h3>{title}</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="line-chart">
        <defs>
          <linearGradient id={areaId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BLUE_SCALE.b300} stopOpacity="0.35" />
            <stop offset="100%" stopColor={BLUE_SCALE.b100} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        {tickValues.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={`line-tick-${tick}`}>
              <line x1={margin.left} y1={y} x2={width - margin.right} y2={y} stroke="#dbeafe" strokeWidth="1" />
              <text x={margin.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#475569">
                {fmt(tick)}
              </text>
            </g>
          );
        })}
        <line x1={margin.left} y1={height - margin.bottom} x2={width - margin.right} y2={height - margin.bottom} stroke="#1e3a8a" strokeWidth="1.2" />
        <line x1={margin.left} y1={margin.top} x2={margin.left} y2={height - margin.bottom} stroke="#1e3a8a" strokeWidth="1.2" />
        {values.length > 1 ? (
          <polygon
            points={`${points} ${xFor(values.length - 1)},${height - margin.bottom} ${xFor(0)},${height - margin.bottom}`}
            fill={`url(#${areaId})`}
          />
        ) : null}
        <polyline fill="none" stroke={stroke} strokeWidth="3" points={points} />
        {values.map((v, i) => (
          <circle key={`pt-${i}`} cx={xFor(i)} cy={yFor(v)} r="3" fill={stroke}>
            <title>{`${labels[i]}: ${v}`}</title>
          </circle>
        ))}
        {labels.map((label, i) => (
          <text key={`lbl-${label}-${i}`} x={xFor(i)} y={height - margin.bottom + 14} textAnchor="middle" fontSize="10" fill="#64748b">
            {label}
          </text>
        ))}
        <text x={margin.left + innerWidth / 2} y={height - 10} textAnchor="middle" fontSize="12" fill="#334155">
          {xLabel}
        </text>
        <text
          x={14}
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${margin.top + innerHeight / 2})`}
          fontSize="12"
          fill="#334155"
        >
          {yLabel}
        </text>
      </svg>
    </div>
  );
}

type SectionKey = 'home' | 'new-field' | 'upload' | 'analytics' | 'model' | 'explore' | 'settings';

const SECTION_CARDS: Array<{ key: SectionKey; title: string; description: string }> = [
  { key: 'new-field', title: 'Create New Field', description: 'Search location, draw field boundary, and place traps.' },
  { key: 'upload', title: 'Upload Trap Images', description: 'Choose an existing field and trap, then upload images.' },
  { key: 'analytics', title: 'Monitoring Analytics', description: 'Review detections by date, field, and trap.' },
  { key: 'model', title: 'Insect Model Overview', description: 'Inspect model quality and live runtime performance metrics.' },
  { key: 'explore', title: 'Exploratory Analysis', description: 'Ask questions about your uploads and detection trends.' },
  { key: 'settings', title: 'Account Settings', description: 'View account profile and access scope.' },
];

export default function DashboardPage() {
  const { token, user, logout } = useAuth();

  const [section, setSection] = useState<SectionKey>('home');
  const [uploads, setUploads] = useState<UploadSummary[]>([]);
  const [lastBatch, setLastBatch] = useState<UploadBatchResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [insights, setInsights] = useState<InsightDashboard | null>(null);
  const [insightDetail, setInsightDetail] = useState<UploadDetail | null>(null);
  const [modelStats, setModelStats] = useState<ModelStats | null>(null);
  const [environmentOverview, setEnvironmentOverview] = useState<EnvironmentOverview | null>(null);
  const [fieldOptions, setFieldOptions] = useState<FieldMapSummary[]>([]);
  const [envFieldDetail, setEnvFieldDetail] = useState<FieldMapDetail | null>(null);
  const [error, setError] = useState('');

  const [selectedTrap, setSelectedTrap] = useState<TrapPoint | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [preferredUploadFieldId, setPreferredUploadFieldId] = useState<string | null>(null);
  const [uploadMode, setUploadMode] = useState<'trap' | 'field'>('trap');

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [files, setFiles] = useState<FileList | null>(null);
  const [busy, setBusy] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatFieldId, setChatFieldId] = useState('');
  const [chatYear, setChatYear] = useState<string>('all');
  const [chatRange, setChatRange] = useState<string>('all');
  const [envDataScope, setEnvDataScope] = useState<string>('all');
  const [insightTrapIdFilter, setInsightTrapIdFilter] = useState('');
  const [insightTrapFilter, setInsightTrapFilter] = useState('');
  const [insightStartDate, setInsightStartDate] = useState('');
  const [insightEndDate, setInsightEndDate] = useState('');
  const [insightMinDetections, setInsightMinDetections] = useState('');
  const [insightMaxDetections, setInsightMaxDetections] = useState('');
  const [insightMinConfidence, setInsightMinConfidence] = useState('');
  const [insightBusy, setInsightBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [envBusy, setEnvBusy] = useState(false);
  const [envSyncFieldId, setEnvSyncFieldId] = useState('');
  const [timeseriesBusy, setTimeseriesBusy] = useState(false);
  const [selectedWeekIndex, setSelectedWeekIndex] = useState<number>(0);
  const [timeseries, setTimeseries] = useState<FieldTimeseries | null>(null);
  const [chatMessages, setChatMessages] = useState<
    Array<{ role: 'user' | 'assistant'; text: string; reportHref?: string; reportFilename?: string }>
  >([
    {
      role: 'assistant',
      text: 'Ask me anything about trap uploads, detections, fields, and trends in your current data scope.',
    },
  ]);
  const selectedFiles = useMemo(() => (files ? Array.from(files) : []), [files]);
  const uploadValidationErrors = useMemo(
    () =>
      validateUploadInput({
        files: selectedFiles,
        startDate,
        endDate,
        selectedTrapId: selectedTrap?.id ?? null,
        selectedFieldId,
        requireTrapSelection: uploadMode === 'trap',
      }),
    [selectedFiles, startDate, endDate, selectedTrap, selectedFieldId, uploadMode]
  );

  const fmt = (value: number | null | undefined, digits: number = 1) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '-';
    return Number(value).toFixed(digits);
  };

  const parseEnvScope = (scope: string): { year?: number; weeks?: number; allData: boolean } => {
    if (scope.startsWith('year:')) {
      const year = Number.parseInt(scope.split(':')[1], 10);
      return Number.isFinite(year) ? { year, allData: true } : { allData: true };
    }
    if (scope.startsWith('weeks:')) {
      const weeks = Number.parseInt(scope.split(':')[1], 10);
      return Number.isFinite(weeks) ? { weeks, allData: false } : { allData: true };
    }
    return { allData: true };
  };

  const buildInsightQuery = () => {
    const parts: string[] = [];
    if (envSyncFieldId) parts.push(`field_id=${encodeURIComponent(envSyncFieldId)}`);
    if (insightTrapIdFilter.trim()) parts.push(`trap_id=${encodeURIComponent(insightTrapIdFilter.trim())}`);
    if (insightTrapFilter.trim()) parts.push(`trap_code=${encodeURIComponent(insightTrapFilter.trim())}`);
    if (insightStartDate) parts.push(`start_date=${encodeURIComponent(insightStartDate)}`);
    if (insightEndDate) parts.push(`end_date=${encodeURIComponent(insightEndDate)}`);
    if (insightMinDetections) parts.push(`min_detections=${encodeURIComponent(insightMinDetections)}`);
    if (insightMaxDetections) parts.push(`max_detections=${encodeURIComponent(insightMaxDetections)}`);
    if (insightMinConfidence) parts.push(`min_confidence=${encodeURIComponent(insightMinConfidence)}`);
    return parts.length > 0 ? `?${parts.join('&')}` : '';
  };

  const loadUploads = async () => {
    if (!token) return;
    const uploadRows = await apiClient.get<UploadSummary[]>('/api/analysis/uploads', token);
    setUploads(uploadRows);
  };

  const loadAnalytics = async () => {
    if (!token) return;
    const { year: selectedYear } = parseEnvScope(envDataScope);
    const parts: string[] = [];
    if (selectedYear) parts.push(`year=${selectedYear}`);
    if (envSyncFieldId) parts.push(`field_id=${encodeURIComponent(envSyncFieldId)}`);
    const query = parts.length > 0 ? `?${parts.join('&')}` : '';
    const payload = await apiClient.get<AnalyticsOverview>(`/api/analytics/overview${query}`, token);
    setAnalytics(payload);
    const nextYears = payload.available_years ?? [];
    if (nextYears.length > 0) setAvailableYears(nextYears);
    if (selectedYear && nextYears.length > 0 && !nextYears.includes(selectedYear)) {
      setEnvDataScope('all');
    }
    if (chatYear !== 'all' && nextYears.length > 0 && !nextYears.includes(Number.parseInt(chatYear, 10))) {
      setChatYear('all');
    }
  };

  const loadInsights = async () => {
    if (!token) return;
    setInsightBusy(true);
    try {
      const payload = await apiClient.get<InsightDashboard>(`/api/analytics/insights${buildInsightQuery()}`, token);
      setInsights(payload);
    } finally {
      setInsightBusy(false);
    }
  };

  const exportInsightsCsv = async () => {
    if (!token) return;
    setExportBusy(true);
    setError('');
    try {
      const csv = await apiClient.getText(`/api/analytics/insights/export.csv${buildInsightQuery()}`, token);
      const href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = href;
      link.download = 'insight-dashboard-export.csv';
      link.click();
      URL.revokeObjectURL(href);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export insight data');
    } finally {
      setExportBusy(false);
    }
  };

  const inspectInsightUpload = async (uploadId: number) => {
    if (!token) return;
    setError('');
    try {
      const payload = await apiClient.get<UploadDetail>(`/api/analysis/uploads/${uploadId}`, token);
      setInsightDetail(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load image result');
    }
  };

  const loadModelStats = async () => {
    if (!token) return;
    const payload = await apiClient.get<ModelStats>('/api/analysis/model-stats', token);
    setModelStats(payload);
  };

  const loadAvailableYears = async (fieldId?: string) => {
    if (!token) return;
    const query = fieldId ? `?field_id=${encodeURIComponent(fieldId)}` : '';
    const payload = await apiClient.get<AnalyticsOverview>(`/api/analytics/overview${query}`, token);
    const nextYears = payload.available_years ?? [];
    setAvailableYears(nextYears);
    if (chatYear !== 'all' && !nextYears.includes(Number.parseInt(chatYear, 10))) {
      setChatYear('all');
    }
  };

  const loadEnvironmentOverview = async () => {
    if (!token) return;
    const { year: selectedYear } = parseEnvScope(envDataScope);
    const query = selectedYear ? `?year=${selectedYear}` : '';
    const payload = await apiClient.get<EnvironmentOverview>(`/api/environment/overview${query}`, token);
    setEnvironmentOverview(payload);
    const nextYears = payload.available_years ?? [];
    if (nextYears.length > 0) setAvailableYears(nextYears);
    if (!envSyncFieldId && payload.fields.length > 0) {
      const preferred = payload.fields.find((row) => row.records > 0) ?? payload.fields[0];
      setEnvSyncFieldId(preferred.field_id);
    }
  };

  const loadFieldOptions = async () => {
    if (!token) return;
    const rows = await apiClient.get<FieldMapSummary[]>('/api/map/fields', token);
    setFieldOptions(rows);
    if (!chatFieldId && rows.length > 0) {
      setChatFieldId(rows[0].id);
    }
  };

  const loadFieldTimeseries = async (fieldId: string) => {
    if (!token || !fieldId) return;
    const { year: selectedYear, weeks: selectedWeeks, allData } = parseEnvScope(envDataScope);
    const parts = [allData ? 'all_data=true' : `weeks=${selectedWeeks ?? 10}`];
    if (selectedYear) parts.push(`year=${selectedYear}`);
    const query = parts.join('&');
    const payload = await apiClient.get<FieldTimeseries>(`/api/environment/fields/${fieldId}/timeseries?${query}`, token);
    setTimeseries(payload);
  };

  useEffect(() => {
    if (!token) return;
    void loadUploads().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load uploads');
    });
    void loadModelStats().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load model stats');
    });
  }, [token]);

  useEffect(() => {
    if (section !== 'analytics' || !token) return;
    void Promise.all([loadAnalytics(), loadInsights(), loadEnvironmentOverview(), loadFieldOptions()]).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    });
  }, [section, token, envDataScope, envSyncFieldId]);

  useEffect(() => {
    if (section !== 'explore' || !token) return;
    void loadFieldOptions().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load fields');
    });
  }, [section, token]);

  useEffect(() => {
    if (section !== 'upload' || !token) return;
    void loadFieldOptions().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load fields');
    });
  }, [section, token]);

  useEffect(() => {
    if (section !== 'explore' || !token) return;
    void loadAvailableYears(chatFieldId || undefined).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load years');
    });
  }, [section, token, chatFieldId]);

  useEffect(() => {
    if (section !== 'analytics' || !token || !envSyncFieldId) return;
    setTimeseriesBusy(true);
    void loadFieldTimeseries(envSyncFieldId)
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load field timeseries');
      })
      .finally(() => setTimeseriesBusy(false));
  }, [section, token, envSyncFieldId, envDataScope]);

  useEffect(() => {
    if (section !== 'analytics' || !token || !envSyncFieldId) return;
    void apiClient
      .get<FieldMapDetail>(`/api/map/fields/${envSyncFieldId}`, token)
      .then((payload) => setEnvFieldDetail(payload))
      .catch(() => setEnvFieldDetail(null));
  }, [section, token, envSyncFieldId]);

  useEffect(() => {
    const count = timeseries?.population_weekly.length ?? 0;
    if (count > 0) {
      setSelectedWeekIndex(count - 1);
    } else {
      setSelectedWeekIndex(0);
    }
  }, [timeseries?.field_id, timeseries?.selected_year, timeseries?.population_weekly.length]);

  useEffect(() => {
    if (section !== 'upload' || !token) return;

    const latestTrapUpload = uploads.find((item) => item.trap_id && item.field_id);
    if (!latestTrapUpload || !latestTrapUpload.trap_id) return;

    const nextFieldId = latestTrapUpload.field_id;
    setPreferredUploadFieldId(nextFieldId);
    setSelectedFieldId(nextFieldId);

    void (async () => {
      try {
        const detail = await apiClient.get<FieldMapDetail>(`/api/map/fields/${nextFieldId}`, token);
        const trap = detail.traps.find((item) => item.id === latestTrapUpload.trap_id) ?? null;
        setSelectedTrap(trap);
      } catch {
        setSelectedTrap(null);
      }
    })();
  }, [section, token, uploads]);

  const uploadBatch = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) {
      setError('You must be signed in to upload images.');
      return;
    }
    if (uploadValidationErrors.length > 0) {
      setError(uploadValidationErrors[0]);
      return;
    }
    if (!selectedFieldId) {
      setError('Select a field first.');
      return;
    }
    if (uploadMode === 'trap' && !selectedTrap) {
      setError('Select a trap marker on the map first.');
      return;
    }

    setError('');
    setBusy(true);

    try {
      const formData = new FormData();
      formData.set('start_date', startDate);
      formData.set('end_date', endDate);
      formData.set('field_id', selectedFieldId);
      if (uploadMode === 'trap' && selectedTrap) {
        formData.set('trap_id', selectedTrap.id);
        formData.set('trap_code', selectedTrap.name);
      } else {
        formData.set('trap_code', 'FIELD_BATCH');
      }
      selectedFiles.forEach((file) => formData.append('images', file));

      const response = await apiClient.postForm<UploadBatchResponse>('/api/analysis/upload-range', formData, token);
      setLastBatch(response);
      await loadUploads();
      if (section === 'analytics') {
        await loadAnalytics();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const renderHome = () => (
    <section className="card">
      <h2>Platform Home</h2>
      <div className="home-welcome">
        <h3>Welcome back, {user?.full_name ?? 'Researcher'}</h3>
        <p>Pick a module below to continue mapping fields, uploading trap images, or reviewing model outcomes.</p>
      </div>
      <div className="hub-grid">
        {SECTION_CARDS.map((card) => (
          <button key={card.key} className="hub-card" type="button" onClick={() => setSection(card.key)}>
            <strong>{card.title}</strong>
            <span>{card.description}</span>
          </button>
        ))}
      </div>
    </section>
  );

  const renderMapSection = (title: string, withUploadForm: boolean, createOnly: boolean = false) => (
    <>
      {token ? (
        <FieldMapManager
          token={token}
          selectedTrapId={selectedTrap?.id ?? ''}
          uploadOnly={withUploadForm}
          autoSelectFirstField={withUploadForm ? false : !createOnly}
          createOnly={createOnly}
          preferredFieldId={withUploadForm ? preferredUploadFieldId : null}
          onTrapSelect={(trap, fieldId) => {
            setSelectedTrap(trap);
            setSelectedFieldId(fieldId);
          }}
        />
      ) : null}

      {withUploadForm ? (
        <section className="card">
          <h2>{title}</h2>
          <p>
            {uploadMode === 'trap' ? (
              <>
                Active trap: <strong>{selectedTrap?.name ?? 'None selected'}</strong>
                {selectedTrap ? ` (${selectedTrap.id})` : ''}
              </>
            ) : (
              <>
                Field-level batch: <strong>{fieldOptions.find((field) => field.id === selectedFieldId)?.name ?? 'No field selected'}</strong>
              </>
            )}
          </p>
          <form onSubmit={uploadBatch} className="form">
            <fieldset className="segmented-fieldset">
              <legend>Batch metadata mode</legend>
              <label>
                <input
                  type="radio"
                  name="uploadMode"
                  value="trap"
                  checked={uploadMode === 'trap'}
                  onChange={() => setUploadMode('trap')}
                />
                Exact trap
              </label>
              <label>
                <input
                  type="radio"
                  name="uploadMode"
                  value="field"
                  checked={uploadMode === 'field'}
                  onChange={() => {
                    setUploadMode('field');
                    setSelectedTrap(null);
                  }}
                />
                Field-level batch
              </label>
            </fieldset>
            {uploadMode === 'field' ? (
              <label>
                Batch Field
                <select value={selectedFieldId ?? ''} onChange={(event) => setSelectedFieldId(event.target.value || null)} required>
                  <option value="">Select field for batch</option>
                  {fieldOptions.map((field) => (
                    <option key={field.id} value={field.id}>
                      {field.name} ({field.trap_count} traps)
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              Start Date
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
            </label>
            <label>
              End Date
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
            </label>
            <label>
              Images
              <input
                type="file"
                accept={ACCEPTED_UPLOAD_EXTENSIONS.join(',')}
                multiple
                onChange={(e) => setFiles(e.target.files)}
                required
              />
            </label>
            {uploadValidationErrors.length > 0 ? (
              <div className="error validation-list" role="alert">
                {uploadValidationErrors.map((message) => (
                  <p key={message}>{message}</p>
                ))}
              </div>
            ) : null}
            <button type="submit" disabled={busy || uploadValidationErrors.length > 0}>
              {busy ? 'Processing...' : uploadMode === 'field' ? 'Upload Batch + Run Model' : 'Upload + Run Model'}
            </button>
          </form>
        </section>
      ) : null}
    </>
  );

  const renderAnalytics = () => (
    <section className="card">
      <h2>Analytics</h2>
      {(() => {
        const popRows = timeseries?.population_weekly ?? [];
        const weekLabels = popRows.map((row) => row.week_start.slice(5));
        const weekDetections = popRows.map((row) => row.total_population);
        let running = 0;
        const cumulative = weekDetections.map((value) => {
          running += value;
          return running;
        });
        const trapAggregates = new Map<string, { images: number; detections: number }>();
        for (const row of timeseries?.trap_weekly ?? []) {
          const baseTrap = row.trap_code.replace(/-S[AB]$/, '');
          const prev = trapAggregates.get(baseTrap) ?? { images: 0, detections: 0 };
          prev.images += row.uploads;
          prev.detections += row.total_population;
          trapAggregates.set(baseTrap, prev);
        }
        const trapSeries = Array.from(trapAggregates.entries())
          .map(([trapCode, value]) => ({
            trapCode,
            images: value.images,
            detections: value.detections,
            avgPerImage: value.images > 0 ? value.detections / value.images : 0,
          }))
          .sort((a, b) => b.detections - a.detections)
          .slice(0, 10);
        const scope = parseEnvScope(envDataScope);
        const periodLabel = scope.year ? `Year ${scope.year}` : scope.weeks ? `Last ${scope.weeks} Weeks` : 'All-Time';
        const weekCount = timeseries?.population_weekly.length ?? 0;
        const safeWeekIndex = Math.min(Math.max(selectedWeekIndex, 0), Math.max(weekCount - 1, 0));
        const selectedWeek = timeseries?.population_weekly[safeWeekIndex];
        const selectedWeekStart = selectedWeek?.week_start ?? null;
        const selectedWeekTrapRows = (timeseries?.trap_weekly ?? [])
          .filter((row) => row.week_start === selectedWeekStart)
          .sort((a, b) => b.total_population - a.total_population);
        const selectedWeekTrapTop = selectedWeekTrapRows.slice(0, 20);
        const weekTrapMap = new Map(selectedWeekTrapRows.map((row) => [row.trap_code, row.total_population]));
        const baseTraps = envFieldDetail?.traps ?? [];
        const maxSideCount = Math.max(
          1,
          ...baseTraps.flatMap((trap) => [weekTrapMap.get(`${trap.name}-SA`) ?? 0, weekTrapMap.get(`${trap.name}-SB`) ?? 0])
        );
        const trapLats = baseTraps.map((trap) => trap.lat);
        const trapLngs = baseTraps.map((trap) => trap.lng);
        const minLat = trapLats.length ? Math.min(...trapLats) : 0;
        const maxLat = trapLats.length ? Math.max(...trapLats) : 1;
        const minLng = trapLngs.length ? Math.min(...trapLngs) : 0;
        const maxLng = trapLngs.length ? Math.max(...trapLngs) : 1;
        const latSpan = Math.max(maxLat - minLat, 1e-9);
        const lngSpan = Math.max(maxLng - minLng, 1e-9);
        const toMapXY = (lat: number, lng: number) => {
          const width = 700;
          const height = 420;
          const margin = 32;
          const x = margin + ((lng - minLng) / lngSpan) * (width - margin * 2);
          const y = margin + (1 - (lat - minLat) / latSpan) * (height - margin * 2);
          return { x, y };
        };
        const heatColor = (value: number) => {
          const ratio = Math.max(0, Math.min(1, value / maxSideCount));
          if (ratio < 0.2) return '#dbeafe';
          if (ratio < 0.4) return '#93c5fd';
          if (ratio < 0.6) return '#60a5fa';
          if (ratio < 0.8) return '#2563eb';
          return '#1e3a8a';
        };
        const totalUploads = (timeseries?.population_weekly ?? []).reduce((sum, row) => sum + row.uploads, 0);
        const totalDetections = (timeseries?.population_weekly ?? []).reduce((sum, row) => sum + row.total_population, 0);
        const avgPerImage = totalUploads > 0 ? totalDetections / totalUploads : 0;
        return (
          <>
            <p>
              Scope: <strong>{analytics?.scope ?? '-'}</strong>
            </p>
            <p>Use the charts below to compare weekly population signals with weather and stress indicators.</p>
            <div className="card">
              <h3>Insight Dashboard</h3>
              <p>
                Review image-level prediction results, operational KPIs, trends, and export-ready monitoring data from stored detections.
              </p>
              <div className="map-toolbar">
                <select value={envSyncFieldId} onChange={(event) => setEnvSyncFieldId(event.target.value)}>
                  <option value="">All accessible fields</option>
                  {fieldOptions.map((field) => (
                    <option key={`insight-field-${field.id}`} value={field.id}>
                      {field.name}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={insightTrapIdFilter}
                  onChange={(event) => setInsightTrapIdFilter(event.target.value)}
                  placeholder="Trap ID"
                  aria-label="Insight trap ID filter"
                />
                <input
                  type="text"
                  value={insightTrapFilter}
                  onChange={(event) => setInsightTrapFilter(event.target.value)}
                  placeholder="Trap code"
                  aria-label="Insight trap code filter"
                />
                <input
                  type="date"
                  value={insightStartDate}
                  onChange={(event) => setInsightStartDate(event.target.value)}
                  aria-label="Insight start date"
                />
                <input
                  type="date"
                  value={insightEndDate}
                  onChange={(event) => setInsightEndDate(event.target.value)}
                  aria-label="Insight end date"
                />
                <input
                  type="number"
                  min="0"
                  value={insightMinDetections}
                  onChange={(event) => setInsightMinDetections(event.target.value)}
                  placeholder="Min detections"
                  aria-label="Minimum detections filter"
                />
                <input
                  type="number"
                  min="0"
                  value={insightMaxDetections}
                  onChange={(event) => setInsightMaxDetections(event.target.value)}
                  placeholder="Max detections"
                  aria-label="Maximum detections filter"
                />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={insightMinConfidence}
                  onChange={(event) => setInsightMinConfidence(event.target.value)}
                  placeholder="Min confidence"
                  aria-label="Minimum confidence filter"
                />
                <button type="button" disabled={insightBusy} onClick={() => void loadInsights()}>
                  {insightBusy ? 'Loading Insights...' : 'Apply Filters'}
                </button>
                <button type="button" disabled={exportBusy || insightBusy} onClick={() => void exportInsightsCsv()}>
                  {exportBusy ? 'Exporting...' : 'Export CSV'}
                </button>
              </div>
              <div className="insight-kpis">
                <div>
                  <span>Processed Images</span>
                  <strong>{insights?.kpis.processed_images ?? 0}</strong>
                </div>
                <div>
                  <span>Total Detections</span>
                  <strong>{insights?.kpis.total_detections ?? 0}</strong>
                </div>
                <div>
                  <span>Avg Detections / Image</span>
                  <strong>{fmt(insights?.kpis.avg_detections_per_image, 2)}</strong>
                </div>
                <div>
                  <span>Highest Field</span>
                  <strong>{insights?.kpis.highest_activity_field?.field_name ?? '-'}</strong>
                </div>
                <div>
                  <span>Highest Trap</span>
                  <strong>{insights?.kpis.highest_activity_trap?.trap_code ?? '-'}</strong>
                </div>
              </div>
              <p>
                Export context: dataset={insights?.context.dataset_version ?? '-'}, model={insights?.context.model_version ?? '-'}
              </p>
              <div className="grid-2">
                <SimpleBarChart
                  title="Detection Trend Over Time"
                  labels={(insights?.trend ?? []).map((row) => row.capture_date.slice(5))}
                  values={(insights?.trend ?? []).map((row) => row.detections)}
                  xLabel="Date"
                  yLabel="Detections"
                  color={BLUE_SCALE.b700}
                />
                <SimpleBarChart
                  title="Field Comparison"
                  labels={(insights?.comparisons.by_field ?? []).slice(0, 10).map((row) => row.field_name)}
                  values={(insights?.comparisons.by_field ?? []).slice(0, 10).map((row) => row.detections)}
                  xLabel="Field"
                  yLabel="Detections"
                  color={BLUE_SCALE.b600}
                />
              </div>
              <div className="grid-2">
                <SimpleBarChart
                  title="Trap Comparison"
                  labels={(insights?.comparisons.by_trap ?? []).slice(0, 10).map((row) => row.trap_code)}
                  values={(insights?.comparisons.by_trap ?? []).slice(0, 10).map((row) => row.detections)}
                  xLabel="Trap"
                  yLabel="Detections"
                  color={BLUE_SCALE.b500}
                />
                <SimpleBarChart
                  title="Avg Detections Per Trap Image"
                  labels={(insights?.comparisons.by_trap ?? []).slice(0, 10).map((row) => row.trap_code)}
                  values={(insights?.comparisons.by_trap ?? []).slice(0, 10).map((row) => row.avg_detections_per_image)}
                  xLabel="Trap"
                  yLabel="Avg / image"
                  color={BLUE_SCALE.b800}
                />
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Image</th>
                      <th>Field</th>
                      <th>Trap</th>
                      <th>Date</th>
                      <th>Detections</th>
                      <th>Confidence</th>
                      <th>Predictions</th>
                      <th>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(insights?.results ?? []).slice(0, 100).map((row) => (
                      <tr key={row.upload_id}>
                        <td>{row.image_path.split('/').pop() || row.image_path}</td>
                        <td>{row.field_name}</td>
                        <td>{row.trap_id ? `${row.trap_code} (${row.trap_id})` : row.trap_code}</td>
                        <td>{row.capture_date}</td>
                        <td>{row.detection_count}</td>
                        <td>{fmt(row.confidence_avg, 2)}</td>
                        <td>{row.detections.length}</td>
                        <td>
                          <button type="button" className="link-btn table-action" onClick={() => void inspectInsightUpload(row.upload_id)}>
                            Open
                          </button>
                        </td>
                      </tr>
                    ))}
                    {(insights?.results ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={8}>No image-level results match the selected filters.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              {insightDetail ? (
                <div className="insight-detail" role="region" aria-label="Selected image prediction detail">
                  <div>
                    <h4>Image Result #{insightDetail.id}</h4>
                    <p>
                      {insightDetail.field_id} | {insightDetail.trap_code} | {insightDetail.capture_date}
                    </p>
                    <p>{insightDetail.image_path}</p>
                  </div>
                  <button type="button" className="link-btn" onClick={() => setInsightDetail(null)}>
                    Close
                  </button>
                  <ul className="list">
                    {insightDetail.detections.map((detection, index) => (
                      <li key={`${insightDetail.id}-${index}`}>
                        class={detection.class_id}, confidence={detection.confidence.toFixed(3)}, bbox=[
                        {detection.bbox_xyxy.map((value) => value.toFixed(1)).join(', ')}]
                      </li>
                    ))}
                    {insightDetail.detections.length === 0 ? <li>No detections stored for this image.</li> : null}
                  </ul>
                </div>
              ) : null}
            </div>
            <div className="card">
              <h3>Environmental Data (Field Weather + Derived Metrics)</h3>
              <div className="map-toolbar">
                <select value={envSyncFieldId} onChange={(event) => setEnvSyncFieldId(event.target.value)}>
                  <option value="">Select field</option>
                  {(environmentOverview?.fields ?? []).map((row) => (
                    <option key={row.field_id} value={row.field_id}>
                      {row.field_name}
                    </option>
                  ))}
                </select>
                <select id="env-data-scope" value={envDataScope} onChange={(event) => setEnvDataScope(event.target.value)}>
                  <option value="all">All data</option>
                  <option value="weeks:4">Last 4 weeks</option>
                  <option value="weeks:10">Last 10 weeks</option>
                  <option value="weeks:26">Last 26 weeks</option>
                  <option value="weeks:52">Last 52 weeks</option>
                  {availableYears.map((year) => (
                    <option key={`env-year-${year}`} value={`year:${year}`}>
                      Year {year}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!envSyncFieldId || envBusy}
                  onClick={async () => {
                    if (!token || !envSyncFieldId) return;
                    setEnvBusy(true);
                    setError('');
                    try {
                      await apiClient.post(`/api/environment/fields/${envSyncFieldId}/sync`, {}, token);
                      await loadEnvironmentOverview();
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Failed to sync environmental data');
                    } finally {
                      setEnvBusy(false);
                    }
                  }}
                >
                  {envBusy ? 'Syncing...' : 'Fetch / Update Environmental Data'}
                </button>
                <button
                  type="button"
                  disabled={!envSyncFieldId || timeseriesBusy}
                  onClick={async () => {
                    if (!envSyncFieldId) return;
                    setTimeseriesBusy(true);
                    try {
                      await loadFieldTimeseries(envSyncFieldId);
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Failed to refresh charts');
                    } finally {
                      setTimeseriesBusy(false);
                    }
                  }}
                >
                  {timeseriesBusy ? 'Loading Charts...' : 'Refresh Charts'}
                </button>
              </div>
              {(() => {
                const selected = (environmentOverview?.fields ?? []).find((row) => row.field_id === envSyncFieldId);
                if (!selected) {
                  return <p>No environmental summary available for the selected field yet.</p>;
                }
                return (
                  <div className="grid-2">
                    <div>
                      <p>
                        <strong>Field:</strong> {selected.field_name}
                      </p>
                      <p>
                        <strong>Records:</strong> {selected.records}
                      </p>
                      <p>
                        <strong>Coverage:</strong> {selected.start_date ?? '-'} to {selected.end_date ?? '-'}
                      </p>
                    </div>
                    <div>
                      <p>
                        <strong>Latest observed day:</strong> {selected.latest?.date ?? '-'}
                      </p>
                      <p>
                        <strong>Temp (daily mean):</strong> {fmt(selected.latest?.temperature_mean_c)} C | <strong>Rain (daily sum):</strong>{' '}
                        {fmt(selected.latest?.precipitation_mm)} mm
                      </p>
                      <p>
                        <strong>GDD (daily):</strong> {fmt(selected.latest?.gdd_base10_c, 2)} | <strong>Deficit (daily):</strong>{' '}
                        {fmt(selected.latest?.water_deficit_mm, 2)} mm
                      </p>
                    </div>
                  </div>
                );
              })()}
            </div>
            {timeseries ? (
              <>
                <SimpleBarChart
                  title={`${periodLabel} Population (Avg per Image) | ${timeseries.field_name}`}
                  labels={timeseries.population_weekly.map((row) => row.week_start.slice(5))}
                  values={timeseries.population_weekly.map((row) => row.avg_population)}
                  xLabel="Week"
                  yLabel="Avg detections per image"
                  color={BLUE_SCALE.b700}
                />
                <div className="card">
                  <h3>{timeseries.field_name} Overview ({periodLabel})</h3>
                  <div className="grid-2">
                    <div>
                      <p>
                        <strong>Uploads:</strong> {totalUploads}
                      </p>
                      <p>
                        <strong>Total detections:</strong> {totalDetections}
                      </p>
                      <p>
                        <strong>Average per image:</strong> {avgPerImage.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p>
                        <strong>Coverage:</strong> {timeseries.start_date} to {timeseries.end_date}
                      </p>
                      <p>
                        <strong>Weekly points:</strong> {timeseries.population_weekly.length}
                      </p>
                      <p>
                        <strong>Traps active:</strong> {baseTraps.length} ({baseTraps.length * 2} sides)
                      </p>
                    </div>
                  </div>
                  {weekCount > 0 ? (
                    <>
                      <label>
                        Week focus: <strong>{selectedWeek?.week_start ?? '-'}</strong>
                      </label>
                      <input
                        type="range"
                        min={0}
                        max={Math.max(weekCount - 1, 0)}
                        value={safeWeekIndex}
                        onChange={(event) => setSelectedWeekIndex(Number.parseInt(event.target.value, 10) || 0)}
                      />
                      <p>
                        Selected week images={selectedWeek?.uploads ?? 0}, total detections={selectedWeek?.total_population ?? 0}, avg/image=
                        {selectedWeek?.avg_population?.toFixed(2) ?? '0.00'}
                      </p>
                      <div className="grid-2">
                        <SimpleBarChart
                          title={`Trap Development for ${selectedWeek?.week_start ?? '-'} (Detections)`}
                          labels={selectedWeekTrapTop.map((row) => row.trap_code)}
                          values={selectedWeekTrapTop.map((row) => row.total_population)}
                          xLabel="Trap"
                          yLabel="Detections in week"
                          color={BLUE_SCALE.b600}
                        />
                        <div className="card">
                          <h3>Trap Map (A/B Side Counts)</h3>
                          <svg viewBox="0 0 700 420" className="line-chart">
                            <rect x="8" y="8" width="684" height="404" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1" />
                            {baseTraps.map((trap) => {
                              const { x, y } = toMapXY(trap.lat, trap.lng);
                              const sideA = weekTrapMap.get(`${trap.name}-SA`) ?? 0;
                              const sideB = weekTrapMap.get(`${trap.name}-SB`) ?? 0;
                              return (
                                <g key={`trap-map-${trap.id}`}>
                                  <circle cx={x} cy={y} r="5" fill={BLUE_SCALE.b800} />
                                  <text x={x} y={y + 18} textAnchor="middle" fontSize="10" fill={BLUE_SCALE.b800}>
                                    {trap.name}
                                  </text>
                                  <rect x={x - 28} y={y - 34} width="24" height="14" rx="2" fill={heatColor(sideA)} stroke={BLUE_SCALE.b800} strokeWidth="0.7" />
                                  <text x={x - 16} y={y - 24} textAnchor="middle" fontSize="9" fill={BLUE_SCALE.b800}>
                                    {sideA}
                                  </text>
                                  <rect x={x + 4} y={y - 34} width="24" height="14" rx="2" fill={heatColor(sideB)} stroke={BLUE_SCALE.b800} strokeWidth="0.7" />
                                  <text x={x + 16} y={y - 24} textAnchor="middle" fontSize="9" fill={BLUE_SCALE.b800}>
                                    {sideB}
                                  </text>
                                </g>
                              );
                            })}
                          </svg>
                        </div>
                      </div>
                    </>
                  ) : (
                    <p>No weekly upload data in selected scope.</p>
                  )}
                </div>
                <div className="grid-2">
                  <SimpleLineChart
                    title="Weather Trend: Weekly Average Temperature (°C)"
                    labels={timeseries.weather_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.weather_weekly.map((row) => row.temp_avg)}
                    xLabel="Week"
                    yLabel="Temperature (°C)"
                    stroke={BLUE_SCALE.b600}
                  />
                  <SimpleLineChart
                    title="Weather Trend: Weekly Rain Sum (mm)"
                    labels={timeseries.weather_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.weather_weekly.map((row) => row.rain_sum)}
                    xLabel="Week"
                    yLabel="Rainfall (mm)"
                    stroke={BLUE_SCALE.b500}
                  />
                </div>
                <div className="grid-2">
                  <SimpleLineChart
                    title="Plant Signal: Weekly GDD (base 10)"
                    labels={timeseries.weather_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.weather_weekly.map((row) => row.gdd_avg)}
                    xLabel="Week"
                    yLabel="GDD"
                    stroke={BLUE_SCALE.b700}
                  />
                  <SimpleLineChart
                    title="Plant Signal: Weekly Water Deficit (mm)"
                    labels={timeseries.weather_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.weather_weekly.map((row) => row.deficit_avg)}
                    xLabel="Week"
                    yLabel="Water deficit (mm)"
                    stroke={BLUE_SCALE.b800}
                  />
                </div>
                <div className="grid-2">
                  <SimpleBarChart
                    title={`${periodLabel} Upload Volume`}
                    labels={timeseries.population_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.population_weekly.map((row) => row.uploads)}
                    xLabel="Week"
                    yLabel="Uploads"
                    color={BLUE_SCALE.b600}
                  />
                  <SimpleLineChart
                    title="Weekly Heat Stress Index"
                    labels={timeseries.weather_weekly.map((row) => row.week_start.slice(5))}
                    values={timeseries.weather_weekly.map((row) => row.heat_stress_avg)}
                    xLabel="Week"
                    yLabel="Heat stress (°C above threshold)"
                    stroke={BLUE_SCALE.b700}
                  />
                </div>
                <div className="grid-2">
                  <SimpleBarChart
                    title={`${periodLabel} Total Detections`}
                    labels={weekLabels}
                    values={weekDetections}
                    xLabel="Week"
                    yLabel="Total detections"
                    color={BLUE_SCALE.b500}
                  />
                  <SimpleLineChart
                    title={`${periodLabel} Cumulative Detections`}
                    labels={weekLabels}
                    values={cumulative}
                    xLabel="Week"
                    yLabel="Cumulative detections"
                    stroke={BLUE_SCALE.b800}
                  />
                </div>
                <div className="grid-2">
                  <SimpleBarChart
                    title="Trap-Side Comparison (Detections, Selected Field)"
                    labels={trapSeries.map((row) => row.trapCode)}
                    values={trapSeries.map((row) => row.detections)}
                    xLabel="Trap"
                    yLabel="Detections"
                    color={BLUE_SCALE.b700}
                  />
                  <SimpleBarChart
                    title="Trap Comparison (Avg per Image, Selected Field)"
                    labels={trapSeries.map((row) => row.trapCode)}
                    values={trapSeries.map((row) => Number(row.avgPerImage.toFixed(2)))}
                    xLabel="Trap"
                    yLabel="Avg detections per image"
                    color={BLUE_SCALE.b600}
                  />
                </div>
              </>
            ) : null}
            <div className="card">
              <h3>{user?.role === 'admin' ? 'Admin Scope: all-fields' : `Scope: ${analytics?.scope ?? 'owned-fields'}`}</h3>
              <div className="grid-2">
                <div>
                  <h4>Totals</h4>
                  <p>Uploads: {analytics?.totals.uploads ?? 0}</p>
                  <p>Detections: {analytics?.totals.detections ?? 0}</p>
                  <p>Avg/upload: {analytics?.totals.avg_detection_per_upload ?? 0}</p>
                </div>
                <div>
                  <h4>Daily (latest)</h4>
                  <ul className="list">
                    {(analytics?.daily ?? []).slice(0, 10).map((row) => (
                      <li key={row.capture_date}>
                        {row.capture_date}: uploads={row.uploads}, detections={row.detections}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="grid-2">
                <div>
                  <h4>By Field</h4>
                  <ul className="list">
                    {(analytics?.by_field ?? []).slice(0, 10).map((row) => (
                      <li key={row.field_id}>
                        {row.field_name}: uploads={row.uploads}, detections={row.detections}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>By Trap</h4>
                  <ul className="list">
                    {(analytics?.by_trap ?? []).slice(0, 10).map((row) => (
                      <li key={row.trap_code}>
                        {row.trap_code}: uploads={row.uploads}, detections={row.detections}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </>
        );
      })()}
    </section>
  );

  const renderModelOverview = () => (
    <section className="card">
      <h2>Insect Model Overview</h2>
      <p>Global quality and runtime behavior of the active SWD detection model.</p>
      <div className="grid-2">
        <div className="card">
          <h3>Model Runtime</h3>
          <p>Model file: {modelStats?.model.weights_file ?? '-'}</p>
          <p>Confidence threshold: {modelStats?.model.confidence_threshold ?? '-'}</p>
          <p>Inference image size: {modelStats?.model.image_size ?? '-'}</p>
        </div>
        <div className="card">
          <h3>Evaluation Quality</h3>
          <p>Precision: {modelStats?.evaluation.precision ?? '-'}</p>
          <p>Recall: {modelStats?.evaluation.recall ?? '-'}</p>
          <p>mAP@50: {modelStats?.evaluation.map50 ?? '-'}</p>
          <p>mAP@50:95: {modelStats?.evaluation.map50_95 ?? '-'}</p>
          <p>{modelStats?.evaluation.notes ?? ''}</p>
        </div>
      </div>
      <div className="card">
        <h3>Observed Platform Performance</h3>
        <p>Total uploads processed: {modelStats?.production_observed.total_uploads ?? 0}</p>
        <p>Total detections generated: {modelStats?.production_observed.total_detections ?? 0}</p>
        <p>Average upload confidence: {modelStats?.production_observed.average_upload_confidence ?? 0}</p>
      </div>
    </section>
  );

  const runExploratoryChat = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) return;
    if (!chatFieldId) {
      setError('Select a field first for exploratory analysis.');
      return;
    }
    const question = chatInput.trim();
    if (!question) return;

    setChatBusy(true);
    setError('');
    setChatMessages((prev) => [...prev, { role: 'user', text: question }]);
    setChatInput('');

    try {
      const response = await apiClient.post<ExploratoryReportResponse>(
        '/api/analysis/exploratory-report',
        {
          question,
          field_id: chatFieldId,
          year: chatYear === 'all' ? undefined : Number.parseInt(chatYear, 10),
          all_data: chatRange === 'all',
          weeks: chatRange === 'all' ? undefined : Number.parseInt(chatRange, 10),
        },
        token
      );
      const provider = response.used_openai ? 'OpenAI' : 'Local';
      const providerNote = response.provider_error ? ` (provider error: ${response.provider_error})` : '';
      const summaryLine = `Data snapshot: uploads=${response.context.totals.uploads}, detections=${response.context.totals.detections}, avg confidence=${response.context.totals.avg_confidence}`;
      const blob = new Blob([response.html], { type: 'text/html;charset=utf-8' });
      const reportHref = URL.createObjectURL(blob);
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `${response.answer}\n\n${summaryLine}\nSource: ${provider}${providerNote}`,
          reportHref,
          reportFilename: response.filename,
        },
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', text: err instanceof Error ? err.message : 'Chat request failed.' },
      ]);
    } finally {
      setChatBusy(false);
    }
  };

  const renderExploratoryAnalysis = () => (
    <section className="card">
      <h2>Exploratory Analysis</h2>
      <p>Ask field-specific questions. The chatbot will analyze uploads, trap trends, and weather context for the selected field.</p>
      <div className="card">
        <h3>Data Chatbot</h3>
        <div className="map-toolbar">
          <select value={chatFieldId} onChange={(e) => setChatFieldId(e.target.value)}>
            <option value="">Select field</option>
            {fieldOptions.map((field) => (
              <option key={field.id} value={field.id}>
                {field.name}
              </option>
            ))}
          </select>
          <select value={chatYear} onChange={(e) => setChatYear(e.target.value)}>
            <option value="all">All years</option>
            {availableYears.map((year) => (
              <option key={`chat-year-${year}`} value={String(year)}>
                {year}
              </option>
            ))}
          </select>
          <select value={chatRange} onChange={(e) => setChatRange(e.target.value)}>
            <option value="all">All data</option>
            <option value="5">5 weeks</option>
            <option value="10">10 weeks</option>
            <option value="26">26 weeks</option>
            <option value="52">52 weeks</option>
          </select>
        </div>
        <div className="chat-log">
          {chatMessages.map((message, idx) => (
            <div key={`${message.role}-${idx}`} className={`chat-bubble ${message.role === 'user' ? 'chat-user' : 'chat-assistant'}`}>
              <strong>{message.role === 'user' ? 'You' : 'Assistant'}:</strong> {message.text}
              {message.reportHref ? (
                <div style={{ marginTop: 8 }}>
                  <a href={message.reportHref} download={message.reportFilename ?? 'exploratory-report.html'}>
                    Download HTML report
                  </a>
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <form onSubmit={runExploratoryChat} className="form">
          <label>
            Ask a question
            <input
              placeholder="Example: Which trap had the highest detections in the last uploads?"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
          </label>
          <button type="submit" disabled={chatBusy}>
            {chatBusy ? 'Analyzing...' : 'Ask Chatbot'}
          </button>
        </form>
      </div>
    </section>
  );

  const renderSettings = () => (
    <section className="card">
      <h2>Settings</h2>
      <p>Name: {user?.full_name}</p>
      <p>Email: {user?.email}</p>
      <p>Role: {user?.role}</p>
      <p>Access scope: {user?.role === 'admin' ? 'All fields/uploads/analytics' : 'Only associated fields/uploads/analytics'}</p>
    </section>
  );

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Spotted Wing Drosophila Monitoring Platform</h1>
          <p>
            Logged in as {user?.full_name} ({user?.role})
          </p>
        </div>
        <div className="map-toolbar">
          {section !== 'home' ? (
            <button type="button" onClick={() => setSection('home')}>
              Home
            </button>
          ) : null}
          <button onClick={logout}>Logout</button>
        </div>
      </header>

      {error ? <div className="error card">{error}</div> : null}

      {section === 'home' ? renderHome() : null}
      {section === 'new-field' ? renderMapSection('Create Field Workspace', false, true) : null}
      {section === 'upload' ? renderMapSection('Upload Trap Images to Selected Trap', true) : null}
      {section === 'analytics' ? renderAnalytics() : null}
      {section === 'model' ? renderModelOverview() : null}
      {section === 'explore' ? renderExploratoryAnalysis() : null}
      {section === 'settings' ? renderSettings() : null}
    </div>
  );
}
