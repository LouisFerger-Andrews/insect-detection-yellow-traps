import { describe, expect, it } from 'vitest';
import { validateUploadInput } from '../uploadValidation';

describe('validateUploadInput', () => {
  it('accepts a complete standard upload input', () => {
    const file = new File(['image-bytes'], 'trap-a.jpg', { type: 'image/jpeg' });

    const errors = validateUploadInput({
      files: [file],
      startDate: '2026-04-01',
      endDate: '2026-04-02',
      selectedTrapId: 'trap-1',
      selectedFieldId: 'field-1',
    });

    expect(errors).toEqual([]);
  });

  it('accepts field-level batch uploads without an exact trap', () => {
    const files = [
      new File(['image-a'], 'field-a.jpg', { type: 'image/jpeg' }),
      new File(['image-b'], 'field-b.png', { type: 'image/png' }),
    ];

    const errors = validateUploadInput({
      files,
      startDate: '2026-04-01',
      endDate: '2026-04-02',
      selectedTrapId: null,
      selectedFieldId: 'field-1',
      requireTrapSelection: false,
    });

    expect(errors).toEqual([]);
  });

  it('rejects invalid dates, unsupported images, dataset files, and empty files', () => {
    const unsupported = new File(['data'], 'trap-a.gif', { type: 'image/gif' });
    const dataset = new File(['data'], 'training-sample.jpg', { type: 'image/jpeg' });
    const empty = new File([], 'empty.png', { type: 'image/png' });

    const errors = validateUploadInput({
      files: [unsupported, dataset, empty],
      startDate: '2026-04-03',
      endDate: '2026-04-02',
      selectedTrapId: null,
      selectedFieldId: null,
    });

    expect(errors).toEqual(
      expect.arrayContaining([
        'Select a trap marker on the map first.',
        'End Date must be on or after Start Date.',
        'trap-a.gif: image must be JPG, PNG, or WEBP.',
        'training-sample.jpg: training, validation, and test dataset files cannot be uploaded.',
        'empty.png: file is empty.',
      ])
    );
  });
});
