import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '../DashboardPage';

const getMock = vi.fn();
const postMock = vi.fn();
const postFormMock = vi.fn();
const getTextMock = vi.fn();
const logoutMock = vi.fn();

vi.mock('../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    postForm: (...args: unknown[]) => postFormMock(...args),
    getText: (...args: unknown[]) => getTextMock(...args),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    token: 'token-1',
    user: { full_name: 'Test User', email: 'u@example.com', role: 'admin' },
    logout: logoutMock,
  }),
}));

vi.mock('../../components/FieldMapManager', () => ({
  default: ({
    onTrapSelect,
    uploadOnly,
  }: {
    onTrapSelect: (trap: { id: string; name: string } | null, fieldId: string | null) => void;
    uploadOnly?: boolean;
  }) => (
    <div>
      <p>FieldMapMock {uploadOnly ? 'upload' : 'normal'}</p>
      <button onClick={() => onTrapSelect({ id: 'trap-1', name: 'Trap 1' }, 'field-1')}>Select Trap</button>
    </div>
  ),
}));

function setupGetMocks() {
  getMock.mockImplementation((path: string) => {
    if (path === '/api/analysis/uploads') return Promise.resolve([]);
    if (path === '/api/analysis/model-stats') {
      return Promise.resolve({
        model: { weights_file: 'w.pt', confidence_threshold: 0.5, image_size: 640 },
        evaluation: { precision: 0.8, recall: 0.7, map50: 0.6, map50_95: 0.4, notes: 'ok' },
        production_observed: { total_uploads: 10, total_detections: 42, average_upload_confidence: 0.78 },
      });
    }
    if (path.startsWith('/api/analytics/overview')) {
      return Promise.resolve({
        scope: 'all-fields',
        selected_field_id: null,
        selected_year: null,
        available_years: [2025, 2026],
        totals: { uploads: 10, detections: 42, avg_detection_per_upload: 4.2 },
        daily: [{ capture_date: '2026-01-01', uploads: 2, detections: 8 }],
        by_field: [{ field_id: 'field-1', field_name: 'Field A', uploads: 10, detections: 42 }],
        by_trap: [{ trap_code: 'R01-P01', uploads: 5, detections: 20 }],
      });
    }
    if (path.startsWith('/api/analytics/insights')) {
      return Promise.resolve({
        context: {
          scope: 'all-fields',
          dataset_version: 'metadata-v1.0.0',
          model_version: 'model.pt',
          filters: {
            field_id: 'field-1',
            trap_id: null,
            trap_code: null,
            start_date: null,
            end_date: null,
            min_detections: null,
            max_detections: null,
            min_confidence: null,
          },
        },
        kpis: {
          processed_images: 2,
          total_detections: 8,
          avg_detections_per_image: 4,
          highest_activity_field: {
            field_id: 'field-1',
            field_name: 'Field A',
            images: 2,
            detections: 8,
            avg_detections_per_image: 4,
          },
          highest_activity_trap: {
            trap_code: 'T1',
            images: 2,
            detections: 8,
            avg_detections_per_image: 4,
          },
        },
        trend: [{ capture_date: '2026-01-01', images: 2, detections: 8, avg_detections_per_image: 4 }],
        comparisons: {
          by_field: [{ field_id: 'field-1', field_name: 'Field A', images: 2, detections: 8, avg_detections_per_image: 4 }],
          by_trap: [{ trap_code: 'T1', images: 2, detections: 8, avg_detections_per_image: 4 }],
        },
        results: [
          {
            upload_id: 1,
            image_path: 'storage/uploads/field-1/2026/01/01/T1/image-a.jpg',
            field_id: 'field-1',
            field_name: 'Field A',
            trap_id: 'trap-1',
            trap_code: 'T1',
            capture_date: '2026-01-01',
            detection_count: 8,
            confidence_avg: 0.81,
            detections: [{ class_id: 0, confidence: 0.81, bbox_xyxy: [1, 2, 3, 4] }],
          },
        ],
      });
    }
    if (path === '/api/analysis/uploads/1') {
      return Promise.resolve({
        id: 1,
        user_id: 1,
        field_id: 'field-1',
        trap_id: 'trap-1',
        trap_code: 'T1',
        capture_date: '2026-01-01',
        image_path: 'storage/uploads/field-1/2026/01/01/T1/image-a.jpg',
        detection_count: 8,
        confidence_avg: 0.81,
        created_at: '2026-01-01T00:00:00',
        detections: [{ class_id: 0, confidence: 0.81, bbox_xyxy: [1, 2, 3, 4] }],
      });
    }
    if (path.startsWith('/api/environment/overview')) {
      return Promise.resolve({
        selected_year: null,
        available_years: [2025, 2026],
        fields: [
          {
            field_id: 'field-1',
            field_name: 'Field A',
            records: 10,
            start_date: '2026-01-01',
            end_date: '2026-02-01',
            last_fetch_at: null,
            latest: {
              date: '2026-02-01',
              temperature_mean_c: 10,
              precipitation_mm: 2,
              gdd_base10_c: 1,
              water_deficit_mm: 0.4,
            },
            sources: {},
          },
        ],
      });
    }
    if (path.startsWith('/api/environment/fields/field-1/timeseries')) {
      return Promise.resolve({
        field_id: 'field-1',
        field_name: 'Field A',
        weeks: 2,
        selected_year: null,
        all_data: true,
        start_date: '2026-01-01',
        end_date: '2026-01-08',
        population_weekly: [
          { week_start: '2026-01-01', uploads: 2, avg_population: 2.0, total_population: 4 },
          { week_start: '2026-01-08', uploads: 3, avg_population: 3.0, total_population: 9 },
        ],
        weather_weekly: [
          { week_start: '2026-01-01', temp_avg: 9, rain_sum: 2, gdd_avg: 0.5, deficit_avg: 0.2, heat_stress_avg: 0 },
          { week_start: '2026-01-08', temp_avg: 10, rain_sum: 1, gdd_avg: 0.8, deficit_avg: 0.3, heat_stress_avg: 0 },
        ],
        trap_weekly: [
          { week_start: '2026-01-01', trap_code: 'T1-SA', uploads: 1, avg_population: 2, total_population: 2 },
          { week_start: '2026-01-01', trap_code: 'T1-SB', uploads: 1, avg_population: 2, total_population: 2 },
        ],
      });
    }
    if (path === '/api/map/fields') return Promise.resolve([{ id: 'field-1', name: 'Field A', area_m2: 1000, trap_count: 1 }]);
    if (path === '/api/map/fields/field-1') {
      return Promise.resolve({
        id: 'field-1',
        name: 'Field A',
        area_m2: 1000,
        polygon: [
          { lat: 52.0, lng: 5.0 },
          { lat: 52.01, lng: 5.0 },
          { lat: 52.01, lng: 5.01 },
        ],
        traps: [{ id: 'trap-1', code: 'T1', name: 'T1', lat: 52.005, lng: 5.005, row_index: 1, position_index: 1 }],
      });
    }
    return Promise.resolve({});
  });
}

describe('DashboardPage', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    postFormMock.mockReset();
    getTextMock.mockReset();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:insights') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    setupGetMocks();
    getTextMock.mockResolvedValue('report,Insight dashboard export\n');
    postMock.mockResolvedValue({
      answer: 'ok',
      used_openai: false,
      provider_error: '',
      context: { totals: { uploads: 1, detections: 2, avg_confidence: 0.5 } },
      filename: 'report.html',
      html: '<html>report</html>',
    });
    postFormMock.mockResolvedValue({ total_images: 1, results: [] });
  });

  it('loads analytics section and renders key cards', async () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Monitoring Analytics/i }));
    await waitFor(() => expect(screen.getByText('Environmental Data (Field Weather + Derived Metrics)')).toBeInTheDocument());
    expect(screen.getAllByText(/Scope:/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Totals/)).toBeInTheDocument();
  });

  it('handles upload trap selection and exploratory chat flow', async () => {
    render(<DashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: /Upload Trap Images/i }));
    await waitFor(() => expect(screen.getByText('Upload Trap Images to Selected Trap')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Select Trap' }));
    await waitFor(() => expect(screen.getByText(/Active trap:/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Home' }));
    fireEvent.click(screen.getByRole('button', { name: /Exploratory Analysis/i }));
    await waitFor(() => expect(screen.getByText('Data Chatbot')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Any trend?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask Chatbot' }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/api/analysis/exploratory-report', expect.any(Object), 'token-1'));
  });

  it('supports support-chatbot flow', async () => {
    postMock.mockResolvedValueOnce({
      answer: 'Go to Home > Monitoring Analytics.',
      used_openai: false,
      provider_error: '',
      context: {
        user: { role: 'admin' },
        modules: [],
        workspace: { upload_count: 1, detection_count: 2 },
      },
    });
    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Support Chatbot/i }));
    await waitFor(() => expect(screen.getByText('Navigation & Usage Help')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Ask support'), { target: { value: 'Where are filters?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask Support' }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/api/analysis/support-chat', { question: 'Where are filters?' }, 'token-1'));
  });

  it('renders model and settings sections and supports logout', async () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Insect Model Overview/i }));
    await waitFor(() => expect(screen.getByText('Insect Model Overview')).toBeInTheDocument());
    expect(screen.getByText(/Model file:/)).toBeInTheDocument();
    expect(screen.getByText(/Observed Platform Performance/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Home' }));
    fireEvent.click(screen.getByRole('button', { name: /Account Settings/i }));
    await waitFor(() => expect(screen.getByText('Settings')).toBeInTheDocument());
    expect(screen.getByText(/Access scope:/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
    expect(logoutMock).toHaveBeenCalled();
  });

  it('triggers environment sync and chart refresh in analytics', async () => {
    postMock.mockResolvedValueOnce({ ok: true });
    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Monitoring Analytics/i }));
    await waitFor(() => expect(screen.getByText('Environmental Data (Field Weather + Derived Metrics)')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Fetch / Update Environmental Data' }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/api/environment/fields/field-1/sync', {}, 'token-1'));

    fireEvent.click(screen.getByRole('button', { name: 'Refresh Charts' }));
    await waitFor(() =>
      expect(getMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/environment/fields/field-1/timeseries?'),
        'token-1'
      )
    );
  });

  it('renders insight dashboard filters, inspection, and export', async () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Monitoring Analytics/i }));

    await waitFor(() => expect(screen.getByText('Insight Dashboard')).toBeInTheDocument());
    expect(screen.getByText('Processed Images')).toBeInTheDocument();
    expect(screen.getByText('Total Detections')).toBeInTheDocument();
    expect(screen.getByText('image-a.jpg')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Insight trap ID filter'), { target: { value: 'trap-1' } });
    fireEvent.change(screen.getByLabelText('Insight trap code filter'), { target: { value: 'T1' } });
    fireEvent.change(screen.getByLabelText('Minimum detections filter'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('Maximum detections filter'), { target: { value: '10' } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Apply Filters' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Apply Filters' }));
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith(expect.stringContaining('/api/analytics/insights?'), 'token-1');
      expect(getMock).toHaveBeenCalledWith(expect.stringContaining('trap_id=trap-1'), 'token-1');
      expect(getMock).toHaveBeenCalledWith(expect.stringContaining('max_detections=10'), 'token-1');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    await waitFor(() => expect(screen.getByText('Image Result #1')).toBeInTheDocument());
    expect(screen.getByText(/class=0, confidence=0.810/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(getTextMock).toHaveBeenCalledWith(expect.stringContaining('/api/analytics/insights/export.csv?'), 'token-1'));
  });

  it('validates upload requirements and then uploads successfully', async () => {
    render(<DashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: /Upload Trap Images/i }));
    await waitFor(() => expect(screen.getByText('Upload Trap Images to Selected Trap')).toBeInTheDocument());

    const uploadButton = screen.getByRole('button', { name: 'Upload + Run Model' });
    fireEvent.submit(uploadButton.closest('form')!);
    await waitFor(() => expect(screen.getAllByText('Select a trap marker on the map first.').length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole('button', { name: 'Select Trap' }));
    await waitFor(() => expect(screen.getByText('Trap 1')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('Start Date'), { target: { value: '2026-04-01' } });
    fireEvent.change(screen.getByLabelText('End Date'), { target: { value: '2026-04-02' } });
    const file = new File(['img'], 'trap.jpg', { type: 'image/jpeg' });
    const imagesInput = screen.getByLabelText('Images') as HTMLInputElement;
    Object.defineProperty(imagesInput, 'files', { value: [file] });
    fireEvent.change(imagesInput);

    fireEvent.submit(uploadButton.closest('form')!);
    await waitFor(() => expect(postFormMock).toHaveBeenCalledWith('/api/analysis/upload-range', expect.any(FormData), 'token-1'));

    const submitted = postFormMock.mock.calls[0][1] as FormData;
    expect(submitted.get('start_date')).toBe('2026-04-01');
    expect(submitted.get('end_date')).toBe('2026-04-02');
    expect(submitted.get('field_id')).toBe('field-1');
    expect(submitted.get('trap_id')).toBe('trap-1');
    expect(submitted.get('trap_code')).toBe('Trap 1');
    expect(submitted.getAll('images')).toHaveLength(1);
  });

  it('blocks non-standard upload files before submission', async () => {
    render(<DashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: /Upload Trap Images/i }));
    await waitFor(() => expect(screen.getByText('Upload Trap Images to Selected Trap')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Select Trap' }));
    await waitFor(() => expect(screen.getByText('Trap 1')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('Start Date'), { target: { value: '2026-04-01' } });
    fireEvent.change(screen.getByLabelText('End Date'), { target: { value: '2026-04-02' } });
    const file = new File(['img'], 'training-sample.gif', { type: 'image/gif' });
    const imagesInput = screen.getByLabelText('Images') as HTMLInputElement;
    Object.defineProperty(imagesInput, 'files', { value: [file] });
    fireEvent.change(imagesInput);

    expect(screen.getByText('training-sample.gif: image must be JPG, PNG, or WEBP.')).toBeInTheDocument();
    expect(screen.getByText('training-sample.gif: training, validation, and test dataset files cannot be uploaded.')).toBeInTheDocument();
    fireEvent.submit(screen.getByRole('button', { name: 'Upload + Run Model' }).closest('form')!);
    expect(postFormMock).not.toHaveBeenCalled();
  });

  it('uploads multiple images in field-level batch mode without exact trap placement', async () => {
    render(<DashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: /Upload Trap Images/i }));
    await waitFor(() => expect(screen.getByText('Upload Trap Images to Selected Trap')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('FieldMapMock upload')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Field-level batch'));
    fireEvent.change(screen.getByLabelText('Batch Field'), { target: { value: 'field-1' } });
    fireEvent.change(screen.getByLabelText('Start Date'), { target: { value: '2026-04-01' } });
    fireEvent.change(screen.getByLabelText('End Date'), { target: { value: '2026-04-02' } });

    const files = [
      new File(['img-a'], 'field-a.jpg', { type: 'image/jpeg' }),
      new File(['img-b'], 'field-b.png', { type: 'image/png' }),
    ];
    const imagesInput = screen.getByLabelText('Images') as HTMLInputElement;
    Object.defineProperty(imagesInput, 'files', { value: files });
    fireEvent.change(imagesInput);

    fireEvent.submit(screen.getByRole('button', { name: 'Upload Batch + Run Model' }).closest('form')!);

    await waitFor(() => expect(postFormMock).toHaveBeenCalledWith('/api/analysis/upload-range', expect.any(FormData), 'token-1'));
    const submitted = postFormMock.mock.calls[0][1] as FormData;
    expect(submitted.get('field_id')).toBe('field-1');
    expect(submitted.get('trap_id')).toBeNull();
    expect(submitted.get('trap_code')).toBe('FIELD_BATCH');
    expect(submitted.getAll('images')).toHaveLength(2);
  });

  it('handles exploratory validation and backend error response', async () => {
    postMock.mockRejectedValueOnce(new Error('Chat failed'));

    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: /Exploratory Analysis/i }));
    await waitFor(() => expect(screen.getByText('Data Chatbot')).toBeInTheDocument());

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'status?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask Chatbot' }));
    await waitFor(() => expect(screen.getByText('Select a field first for exploratory analysis.')).toBeInTheDocument());

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'field-1' } });
    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'status now?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask Chatbot' }));
    await waitFor(() => expect(screen.getByText('Chat failed')).toBeInTheDocument());
  });
});
