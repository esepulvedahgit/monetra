import { describe, expect, it } from 'vitest';

import { isCurrentEditorSubmission, localDateString } from '../src/features/editorSafety';

describe('isCurrentEditorSubmission', () => {
  it('does not allow an earlier save to close a reopened editor', () => {
    expect(isCurrentEditorSubmission(3, 4, true)).toBe(false);
    expect(isCurrentEditorSubmission(3, 3, true)).toBe(true);
  });
});

describe('localDateString', () => {
  it('uses the calendar date in the device time zone instead of UTC', () => {
    expect(localDateString(new Date('2026-09-08T02:30:00.000Z'), -180)).toBe('2026-09-07');
  });
});
