import { useEffect, useMemo, useState } from 'react';
import {
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { apiClient } from '../api/client';
import type { FieldMapDetail, FieldMapSummary, LatLng, SearchResult, TrapPoint } from '../types/api';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const cornerIcon = L.divIcon({
  className: 'map-pin map-pin-corner',
  html: '<span></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const draftTrapIcon = L.divIcon({
  className: 'map-pin map-pin-trap-draft',
  html: '<span></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const savedTrapIcon = L.divIcon({
  className: 'map-pin map-pin-trap-saved',
  html: '<span></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

type Props = {
  token: string;
  selectedTrapId: string;
  onTrapSelect: (trap: TrapPoint | null, fieldId: string | null) => void;
  uploadOnly?: boolean;
  autoSelectFirstField?: boolean;
  createOnly?: boolean;
  preferredFieldId?: string | null;
};

function ClickLayer({
  mode,
  onAddPolygonPoint,
  onAddTrapPoint,
}: {
  mode: 'none' | 'draw' | 'trap';
  onAddPolygonPoint: (latLng: LatLng) => void;
  onAddTrapPoint: (latLng: LatLng) => void;
}) {
  useMapEvents({
    click: (event: any) => {
      const point = { lat: event.latlng.lat, lng: event.latlng.lng };
      if (mode === 'draw') {
        onAddPolygonPoint(point);
      }
      if (mode === 'trap') {
        onAddTrapPoint(point);
      }
    },
  });
  return null;
}

function Recenter({ center }: { center: LatLng }) {
  const map = useMap();
  useEffect(() => {
    map.setView([center.lat, center.lng]);
  }, [center.lat, center.lng, map]);
  return null;
}

export default function FieldMapManager({
  token,
  selectedTrapId,
  onTrapSelect,
  uploadOnly = false,
  autoSelectFirstField = true,
  createOnly = false,
  preferredFieldId = null,
}: Props) {
  const [mode, setMode] = useState<'none' | 'draw' | 'trap'>('none');
  const [fieldName, setFieldName] = useState('');
  const [draftPolygon, setDraftPolygon] = useState<LatLng[]>([]);
  const [draftTraps, setDraftTraps] = useState<LatLng[]>([]);
  const [polygonRedoStack, setPolygonRedoStack] = useState<LatLng[]>([]);
  const [trapRedoStack, setTrapRedoStack] = useState<LatLng[]>([]);
  const [fields, setFields] = useState<FieldMapSummary[]>([]);
  const [activeFieldId, setActiveFieldId] = useState<string>('');
  const [activeField, setActiveField] = useState<FieldMapDetail | null>(null);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [mapCenter, setMapCenter] = useState<LatLng>({ lat: 52.1326, lng: 5.2913 });
  const [error, setError] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [renamingBusy, setRenamingBusy] = useState(false);

  const activePolygon = useMemo(
    () => (activeField ? activeField.polygon : draftPolygon),
    [activeField, draftPolygon]
  );

  const loadFields = async () => {
    const summaries = await apiClient.get<FieldMapSummary[]>('/api/map/fields', token);
    setFields(summaries);
    if (!activeFieldId && summaries.length > 0 && autoSelectFirstField) {
      setActiveFieldId(summaries[0].id);
    }
  };

  useEffect(() => {
    void loadFields();
  }, [token]);

  useEffect(() => {
    if (!preferredFieldId) return;
    setActiveFieldId((prev) => (prev === preferredFieldId ? prev : preferredFieldId));
  }, [preferredFieldId]);

  useEffect(() => {
    if (!createOnly) return;
    setActiveFieldId('');
    setActiveField(null);
    setMode('draw');
    onTrapSelect(null, null);
  }, [createOnly]);

  useEffect(() => {
    if (activeFieldId) {
      let cancelled = false;
      void (async () => {
        try {
          const detail = await apiClient.get<FieldMapDetail>(`/api/map/fields/${activeFieldId}`, token);
          if (cancelled) return;
          if (activeFieldId) {
            setActiveField(detail);
            if (detail.polygon.length > 0) {
              setMapCenter(detail.polygon[0]);
            }
          }
        } catch {
          if (!cancelled) {
            setError('Failed to load selected field');
          }
        }
      })();
      return () => {
        cancelled = true;
      };
    } else {
      setActiveField(null);
    }
    onTrapSelect(null, activeFieldId || null);
  }, [activeFieldId, token]);

  const selectedTrap = useMemo(() => {
    if (!activeField || !selectedTrapId) return null;
    return activeField.traps.find((trap) => trap.id === selectedTrapId) ?? null;
  }, [activeField, selectedTrapId]);

  useEffect(() => {
    setRenameValue(selectedTrap?.name ?? '');
  }, [selectedTrap?.id]);

  const onSearch = async () => {
    if (searchText.trim().length < 2) return;
    try {
      const rows = await apiClient.get<SearchResult[]>(
        `/api/map/search?q=${encodeURIComponent(searchText.trim())}`,
        token
      );
      setSearchResults(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    }
  };

  const startDraftField = () => {
    if (uploadOnly) {
      return;
    }
    setActiveFieldId('');
    setActiveField(null);
    setDraftPolygon([]);
    setDraftTraps([]);
    setPolygonRedoStack([]);
    setTrapRedoStack([]);
    onTrapSelect(null, null);
    setMode('draw');
  };

  const undoLastCorner = () => {
    setDraftPolygon((prev) => {
      if (prev.length === 0) return prev;
      setPolygonRedoStack((redo) => [...redo, prev[prev.length - 1]]);
      return prev.slice(0, -1);
    });
  };

  const undoLastTrap = () => {
    setDraftTraps((prev) => {
      if (prev.length === 0) return prev;
      setTrapRedoStack((redo) => [...redo, prev[prev.length - 1]]);
      return prev.slice(0, -1);
    });
  };

  const redoCorner = () => {
    setPolygonRedoStack((prev) => {
      if (prev.length === 0) return prev;
      const restored = prev[prev.length - 1];
      setDraftPolygon((poly) => [...poly, restored]);
      return prev.slice(0, -1);
    });
  };

  const redoTrap = () => {
    setTrapRedoStack((prev) => {
      if (prev.length === 0) return prev;
      const restored = prev[prev.length - 1];
      setDraftTraps((traps) => [...traps, restored]);
      return prev.slice(0, -1);
    });
  };

  const clearDraft = () => {
    setDraftPolygon([]);
    setDraftTraps([]);
    setPolygonRedoStack([]);
    setTrapRedoStack([]);
    onTrapSelect(null, null);
  };

  const saveField = async () => {
    if (uploadOnly) {
      return;
    }
    setError('');
    if (draftPolygon.length < 3) {
      setError('Draw a polygon with at least 3 points.');
      return;
    }
    if (fieldName.trim().length < 2) {
      setError('Field name is required.');
      return;
    }
    try {
      const created = await apiClient.post<FieldMapDetail>(
        '/api/map/fields',
        {
          name: fieldName.trim(),
          polygon: draftPolygon,
          traps: draftTraps,
        },
        token
      );
      setDraftPolygon([]);
      setDraftTraps([]);
      setMode('none');
      setFieldName('');
      await loadFields();
      setActiveFieldId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Field save failed');
    }
  };

  const addTrapToActiveField = async (point: LatLng) => {
    if (!activeFieldId) return;
    try {
      const detail = await apiClient.post<FieldMapDetail>(
        `/api/map/fields/${activeFieldId}/traps`,
        point,
        token
      );
      setActiveField(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add trap');
    }
  };

  const renameSelectedTrap = async () => {
    if (!activeFieldId || !selectedTrap) {
      setError('Select a trap first.');
      return;
    }
    const nextName = renameValue.trim();
    if (!nextName) {
      setError('Trap name cannot be empty.');
      return;
    }
    setError('');
    setRenamingBusy(true);
    try {
      const detail = await apiClient.patch<FieldMapDetail>(
        `/api/map/fields/${activeFieldId}/traps/${selectedTrap.id}`,
        { name: nextName },
        token
      );
      setActiveField(detail);
      const refreshedTrap = detail.traps.find((item) => item.id === selectedTrap.id) ?? null;
      onTrapSelect(refreshedTrap, activeFieldId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rename trap');
    } finally {
      setRenamingBusy(false);
    }
  };

  const onMapTrapClick = (trap: TrapPoint) => {
    onTrapSelect(trap, activeField?.id ?? null);
  };

  return (
    <section className="card">
      <h2>Field Map & Trap Placement</h2>
      <p>
        {uploadOnly
          ? 'Select an existing field and trap marker, then upload images to that exact trap.'
          : 'Search farm, draw field polygon, place traps, then click a trap to upload images to that exact point.'}
      </p>

      {!uploadOnly && searchResults.length > 0 ? (
        <ul className="list">
          {searchResults.map((result, idx) => (
            <li key={`${result.display_name}-${idx}`}>
              <button type="button" onClick={() => setMapCenter({ lat: result.lat, lng: result.lng })}>
                {result.display_name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {error ? <div className="error">{error}</div> : null}
      {mode === 'draw' ? (
        <p>
          Draw mode active: click map to add field corners. Current points: <strong>{draftPolygon.length}</strong>
        </p>
      ) : null}

      {!uploadOnly ? (
        <div className="map-toolbar">
          <input
            placeholder="Search farm location"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
          <button type="button" onClick={onSearch}>
            Search
          </button>
        </div>
      ) : null}

      {!createOnly ? (
        <div className="map-toolbar">
          <select value={activeFieldId} onChange={(event) => setActiveFieldId(event.target.value)}>
            <option value="">{uploadOnly ? 'Select existing field' : 'Draft mode (new field)'}</option>
            {fields.map((field) => (
              <option key={field.id} value={field.id}>
                {field.name} ({field.trap_count} traps)
              </option>
            ))}
          </select>
          {!uploadOnly ? (
            <>
              <button type="button" onClick={startDraftField}>
                New Field Draft
              </button>
              {!activeFieldId ? (
                <>
                  <input
                    placeholder="New field name"
                    value={fieldName}
                    onChange={(event) => setFieldName(event.target.value)}
                  />
                  <button type="button" onClick={saveField}>
                    Save Field
                  </button>
                </>
              ) : null}
            </>
          ) : null}
        </div>
      ) : (
        <div className="map-toolbar">
          <input
            placeholder="New field name"
            value={fieldName}
            onChange={(event) => setFieldName(event.target.value)}
          />
          <button type="button" onClick={saveField}>
            Save Field
          </button>
        </div>
      )}

      <div className="map-wrap">
        <div className="map-overlay">
          <div className="map-panel map-header-main">
            <div className="map-header-left map-menu-bar">
              {!uploadOnly ? (
                <button
                  type="button"
                  className={mode === 'draw' ? 'is-active' : ''}
                  onClick={() => {
                    if (!activeFieldId && draftPolygon.length === 0 && draftTraps.length === 0) {
                      startDraftField();
                      return;
                    }
                    setMode((prev) => (prev === 'draw' ? 'none' : 'draw'));
                  }}
                >
                  Draw Field
                </button>
              ) : null}
              {!uploadOnly ? (
                <button
                  type="button"
                  className={mode === 'trap' ? 'is-active' : ''}
                  onClick={() => setMode((prev) => (prev === 'trap' ? 'none' : 'trap'))}
                >
                  Place Traps
                </button>
              ) : (
                <span className="map-mode-hint">Select an existing trap marker</span>
              )}
            </div>

            <div className="map-header-center map-edit-bar">
              {mode === 'draw' ? (
                <>
                  <button type="button" onClick={undoLastCorner} disabled={draftPolygon.length === 0}>
                    Undo Corner
                  </button>
                  <button type="button" onClick={redoCorner} disabled={polygonRedoStack.length === 0}>
                    Redo Corner
                  </button>
                  <button
                    type="button"
                    onClick={clearDraft}
                    disabled={draftPolygon.length === 0 && draftTraps.length === 0}
                  >
                    Clear Draft
                  </button>
                </>
              ) : null}
              {mode === 'trap' ? (
                <>
                  <button type="button" onClick={undoLastTrap} disabled={draftTraps.length === 0 || !!activeFieldId}>
                    Undo Trap
                  </button>
                  <button type="button" onClick={redoTrap} disabled={trapRedoStack.length === 0 || !!activeFieldId}>
                    Redo Trap
                  </button>
                  <button
                    type="button"
                    onClick={clearDraft}
                    disabled={draftPolygon.length === 0 && draftTraps.length === 0}
                  >
                    Clear Draft
                  </button>
                </>
              ) : null}
              {mode === 'none' && !uploadOnly ? (
                <span className="map-mode-hint">Select Draw Field or Place Traps</span>
              ) : null}
            </div>
            <div className="map-header-right" />
          </div>
        </div>

        <MapContainer center={[mapCenter.lat, mapCenter.lng]} zoom={16} style={{ height: 460, width: '100%' }}>
          <Recenter center={mapCenter} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickLayer
            mode={uploadOnly ? 'none' : mode}
            onAddPolygonPoint={(point) => {
              setDraftPolygon((prev) => [...prev, point]);
              setPolygonRedoStack([]);
            }}
            onAddTrapPoint={(point) => {
              if (uploadOnly) {
                return;
              }
              if (activeFieldId) {
                void addTrapToActiveField(point);
              } else {
                if (uploadOnly) {
                  setError('Select an existing field before placing/selecting traps.');
                  return;
                }
                setDraftTraps((prev) => [...prev, point]);
                setTrapRedoStack([]);
              }
            }}
          />

          {activePolygon.length >= 3 ? (
            <Polygon positions={activePolygon.map((point) => [point.lat, point.lng] as [number, number])} />
          ) : null}
          {!activeField && draftPolygon.length >= 2 ? (
            <Polyline positions={draftPolygon.map((point) => [point.lat, point.lng] as [number, number])} />
          ) : null}
          {!activeField
            ? draftPolygon.map((point, idx) => (
                <Marker
                  key={`draft-poly-${idx}`}
                  position={[point.lat, point.lng]}
                  icon={cornerIcon}
                  draggable
                  eventHandlers={{
                    dragend: (event) => {
                      const latlng = (event.target as any).getLatLng();
                      setDraftPolygon((prev) =>
                        prev.map((entry, entryIdx) =>
                          entryIdx === idx ? { lat: latlng.lat, lng: latlng.lng } : entry
                        )
                      );
                    },
                  }}
                >
                  <Popup>
                    Corner {idx + 1}
                    <br />
                    Drag to adjust
                  </Popup>
                </Marker>
              ))
            : null}

          {(activeField ? activeField.traps : []).map((trap) => (
            <Marker
              key={trap.id}
              position={[trap.lat, trap.lng]}
              icon={savedTrapIcon}
              eventHandlers={{
                click: () => onMapTrapClick(trap),
              }}
            >
              <Tooltip permanent direction="top" offset={[0, -10]} opacity={0.95}>
                {trap.name}
              </Tooltip>
              <Popup>
                <strong>{trap.name}</strong>
                <br />
                Grid code: {trap.code}
                <br />
                Click marker to select this trap for upload
              </Popup>
            </Marker>
          ))}

          {!activeField
            ? draftTraps.map((point, idx) => (
                <Marker
                  key={`draft-${idx}`}
                  position={[point.lat, point.lng]}
                  icon={draftTrapIcon}
                  draggable
                  eventHandlers={{
                    dragend: (event) => {
                      const latlng = (event.target as any).getLatLng();
                      setDraftTraps((prev) =>
                        prev.map((entry, entryIdx) =>
                          entryIdx === idx ? { lat: latlng.lat, lng: latlng.lng } : entry
                        )
                      );
                    },
                  }}
                >
                  <Popup>
                    Draft trap #{idx + 1}
                    <br />
                    Drag to adjust
                  </Popup>
                </Marker>
              ))
            : null}
        </MapContainer>
      </div>

      {selectedTrap ? <p>Selected trap for upload: {selectedTrap.name}</p> : <p>No trap selected yet.</p>}
      {selectedTrap && !uploadOnly ? (
        <div className="card">
          <h3>Selected Trap</h3>
          <p>
            Current name: <strong>{selectedTrap.name}</strong> (grid {selectedTrap.code})
          </p>
          <div className="form">
            <label>
              Rename trap
              <input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} />
            </label>
            <button type="button" onClick={renameSelectedTrap} disabled={renamingBusy}>
              {renamingBusy ? 'Saving...' : 'Save Trap Name'}
            </button>
            <p>Renaming updates existing uploads linked to this trap automatically.</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
