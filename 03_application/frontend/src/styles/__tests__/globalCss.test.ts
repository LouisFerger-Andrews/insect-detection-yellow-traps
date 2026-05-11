import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const css = readFileSync(resolve(__dirname, '../global.css'), 'utf-8');

describe('responsive global css', () => {
  it('keeps the desktop page constraint intact', () => {
    expect(css).toContain('.page {\n  max-width: 1200px;');
    expect(css).toContain('margin: 0 auto;');
  });

  it('defines tablet rules for single-column content and scrollable tables', () => {
    expect(css).toContain('@media (max-width: 768px)');
    expect(css).toContain('grid-template-columns: minmax(0, 1fr);');
    expect(css).toContain('min-width: 720px;');
  });

  it('defines mobile rules for stacked controls and touch-sized actions', () => {
    expect(css).toContain('@media (max-width: 640px)');
    expect(css).toContain('flex-direction: column;');
    expect(css).toContain('min-height: 44px;');
    expect(css).toContain('height: 360px !important;');
  });
});
