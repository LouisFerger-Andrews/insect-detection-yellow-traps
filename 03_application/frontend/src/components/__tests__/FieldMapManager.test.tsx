import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import FieldMapManager from '../FieldMapManager';

const getMock = vi.fn();
const postMock = vi.fn();
const patchMock = vi.fn();
const setViewMock = vi.fn();

let mapClickHandler: ((event: any) => void) | null = null;

vi.mock('../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    patch: (...args: unknown[]) => patchMock(...args),
  },
}));

vi.mock('leaflet', () => {
  return {
    default: {
      divIcon: vi.fn(() => ({})),
      Icon: {
        Default: Object.assign(function Default() {}, { mergeOptions: vi.fn() }),
      },
    },
  };
});

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  Marker: ({
    children,
    eventHandlers,
  }: {
    children: React.ReactNode;
    eventHandlers?: { click?: () => void };
  }) => (
    <button data-testid="marker" onClick={() => eventHandlers?.click?.()}>
      marker
      {children}
    </button>
  ),
  Polygon: () => <div>polygon</div>,
  Polyline: () => <div>polyline</div>,
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => <div>tile</div>,
  useMap: () => ({ setView: setViewMock }),
  useMapEvents: (events: { click?: (event: any) => void }) => {
    mapClickHandler = events.click ?? null;
    return {};
  },
}));

function baseFieldDetail(name = 'Field A') {
  return {
    id: 'field-1',
    name,
    area_m2: 1000,
    polygon: [
      { lat: 52.0, lng: 5.0 },
      { lat: 52.01, lng: 5.0 },
      { lat: 52.01, lng: 5.01 },
    ],
    traps: [{ id: 'trap-1', code: 'R01-P01', name: 'Trap One', lat: 52.005, lng: 5.005, row_index: 1, position_index: 1 }],
  };
}

function setupGetMock({ searchFails = false } = {}) {
  getMock.mockImplementation((path: string) => {
    if (path === '/api/map/fields') {
      return Promise.resolve([
        { id: 'field-1', name: 'Field A', area_m2: 1000, trap_count: 1 },
        { id: 'field-2', name: 'Field B', area_m2: 2000, trap_count: 0 },
      ]);
    }
    if (path === '/api/map/fields/field-1') {
      return Promise.resolve(baseFieldDetail());
    }
    if (path === '/api/map/fields/field-2') {
      return Promise.resolve({ ...baseFieldDetail('Field B'), id: 'field-2', traps: [] });
    }
    if (path.startsWith('/api/map/search')) {
      if (searchFails) return Promise.reject(new Error('Search unavailable'));
      return Promise.resolve([{ display_name: 'Test Farm', lat: 51.1, lng: 4.2 }]);
    }
    return Promise.resolve([]);
  });
}

describe('FieldMapManager', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
    setViewMock.mockReset();
    mapClickHandler = null;
  });

  it('loads fields and allows selecting trap from map marker', async () => {
    const onTrapSelect = vi.fn();
    setupGetMock();

    render(<FieldMapManager token="token" selectedTrapId="" uploadOnly={true} onTrapSelect={onTrapSelect} />);

    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields', 'token'));
    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields/field-1', 'token'));
    expect(screen.getByText(/Select an existing field and trap marker/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId('marker')[0]);
    expect(onTrapSelect).toHaveBeenCalled();
  });

  it('supports searching and recentering, and surfaces search errors', async () => {
    setupGetMock();
    const onTrapSelect = vi.fn();
    render(<FieldMapManager token="token" selectedTrapId="" uploadOnly={false} onTrapSelect={onTrapSelect} />);

    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields', 'token'));

    fireEvent.change(screen.getByPlaceholderText('Search farm location'), { target: { value: 'fa' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Test Farm' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Test Farm' }));
    await waitFor(() => expect(setViewMock).toHaveBeenCalled());

    getMock.mockImplementationOnce((path: string) => {
      if (path.startsWith('/api/map/search')) return Promise.reject(new Error('Search unavailable'));
      return Promise.resolve([]);
    });
    fireEvent.change(screen.getByPlaceholderText('Search farm location'), { target: { value: 'farm' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByText('Search unavailable')).toBeInTheDocument());
  });

  it('validates draft creation, supports draw/trap interactions, and saves new field', async () => {
    setupGetMock();
    const onTrapSelect = vi.fn();
    postMock.mockImplementation((path: string) => {
      if (path === '/api/map/fields') {
        return Promise.resolve({ ...baseFieldDetail('New Field'), id: 'field-2', traps: [] });
      }
      return Promise.resolve(baseFieldDetail());
    });

    render(<FieldMapManager token="token" selectedTrapId="" uploadOnly={false} onTrapSelect={onTrapSelect} />);
    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields', 'token'));

    fireEvent.click(screen.getByRole('button', { name: 'New Field Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save Field' }));
    await waitFor(() => expect(screen.getByText(/Draw a polygon with at least 3 points/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Draw Field' }));
    await act(async () => {
      mapClickHandler?.({ latlng: { lat: 52.2, lng: 5.2 } });
      mapClickHandler?.({ latlng: { lat: 52.21, lng: 5.2 } });
      mapClickHandler?.({ latlng: { lat: 52.22, lng: 5.2 } });
    });

    fireEvent.change(screen.getByPlaceholderText('New field name'), { target: { value: 'North Field' } });
    fireEvent.click(screen.getByRole('button', { name: 'Place Traps' }));
    await act(async () => {
      mapClickHandler?.({ latlng: { lat: 52.205, lng: 5.205 } });
    });
    expect(screen.getByText(/Draft trap #/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Save Field' }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/api/map/fields', expect.any(Object), 'token'));
  });

  it('supports trap renaming and handles trap add error on active fields', async () => {
    const onTrapSelect = vi.fn();
    setupGetMock();

    patchMock.mockResolvedValue({
      ...baseFieldDetail(),
      traps: [{ id: 'trap-1', code: 'R01-P01', name: 'Renamed Trap', lat: 52.005, lng: 5.005, row_index: 1, position_index: 1 }],
    });
    postMock.mockRejectedValueOnce(new Error('Failed adding trap'));

    render(<FieldMapManager token="token" selectedTrapId="trap-1" uploadOnly={false} onTrapSelect={onTrapSelect} />);

    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields', 'token'));
    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/map/fields/field-1', 'token'));

    const renameInput = screen.getByLabelText('Rename trap');
    fireEvent.change(renameInput, { target: { value: 'Renamed Trap' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Trap Name' }));
    await waitFor(() =>
      expect(patchMock).toHaveBeenCalledWith('/api/map/fields/field-1/traps/trap-1', { name: 'Renamed Trap' }, 'token')
    );

    fireEvent.click(screen.getByRole('button', { name: 'Place Traps' }));
    await act(async () => {
      mapClickHandler?.({ latlng: { lat: 52.3, lng: 5.3 } });
    });
    await waitFor(() => expect(screen.getByText('Failed adding trap')).toBeInTheDocument());
  });

  it('create-only mode forces draft flow', async () => {
    setupGetMock();
    const onTrapSelect = vi.fn();
    render(
      <FieldMapManager
        token="token"
        selectedTrapId=""
        uploadOnly={false}
        createOnly={true}
        onTrapSelect={onTrapSelect}
      />
    );

    await waitFor(() => expect(screen.getByText(/Draw mode active/)).toBeInTheDocument());
    expect(screen.queryByText('New Field Draft')).not.toBeInTheDocument();
    expect(onTrapSelect).toHaveBeenCalledWith(null, null);
  });
});
