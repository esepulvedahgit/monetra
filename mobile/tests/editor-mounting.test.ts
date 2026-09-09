import { describe, expect, it } from 'vitest';

import { shouldKeepEditorMounted } from '../src/features/editorSafety';

describe('shouldKeepEditorMounted', () => {
  it('keeps a pending editor mounted while its screen shows a query error', () => {
    expect(shouldKeepEditorMounted(true, true)).toBe(true);
  });
});
