export const ACCEPTED_UPLOAD_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'] as const;
export const MAX_UPLOAD_SIZE_MB = 20;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;
const DATASET_FILENAME_MARKER = /(^|[^a-z])(train|training|valid|validation|test)([^a-z]|$)/i;

export type UploadValidationInput = {
  files: File[] | null;
  startDate: string;
  endDate: string;
  selectedTrapId?: string | null;
  selectedFieldId?: string | null;
  requireTrapSelection?: boolean;
};

function extensionFor(filename: string): string {
  const dotIndex = filename.lastIndexOf('.');
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : '';
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function validateUploadInput(input: UploadValidationInput): string[] {
  const errors: string[] = [];
  const files = input.files ?? [];
  const requireTrapSelection = input.requireTrapSelection ?? true;

  if (!input.selectedFieldId) {
    errors.push('Select a field first.');
  }
  if (requireTrapSelection && !input.selectedTrapId) {
    errors.push('Select a trap marker on the map first.');
  }
  if (!isIsoDate(input.startDate)) {
    errors.push('Start Date must be a valid date.');
  }
  if (!isIsoDate(input.endDate)) {
    errors.push('End Date must be a valid date.');
  }
  if (isIsoDate(input.startDate) && isIsoDate(input.endDate) && input.startDate > input.endDate) {
    errors.push('End Date must be on or after Start Date.');
  }
  if (files.length === 0) {
    errors.push('Select at least one image.');
  }

  for (const file of files) {
    const extension = extensionFor(file.name);
    if (!ACCEPTED_UPLOAD_EXTENSIONS.includes(extension as (typeof ACCEPTED_UPLOAD_EXTENSIONS)[number])) {
      errors.push(`${file.name}: image must be JPG, PNG, or WEBP.`);
    }
    if (DATASET_FILENAME_MARKER.test(file.name)) {
      errors.push(`${file.name}: training, validation, and test dataset files cannot be uploaded.`);
    }
    if (file.size === 0) {
      errors.push(`${file.name}: file is empty.`);
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      errors.push(`${file.name}: file must be ${MAX_UPLOAD_SIZE_MB} MB or smaller.`);
    }
  }

  return errors;
}
