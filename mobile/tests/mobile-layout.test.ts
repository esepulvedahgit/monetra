import { describe, expect, it } from 'vitest';

import { mobileContentInsets, mobileTabBarLayout } from '../src/layout/mobileLayout';

describe('mobileContentInsets', () => {
  it('preserves the system gesture area below scrollable content', () => {
    expect(mobileContentInsets({ top: 24, bottom: 20, left: 0, right: 0 })).toEqual({
      paddingTop: 24,
      paddingBottom: 44,
      paddingLeft: 16,
      paddingRight: 16,
    });
  });

  it('adds horizontal safe-area space on devices with side insets', () => {
    expect(mobileContentInsets({ top: 0, bottom: 0, left: 30, right: 24 })).toMatchObject({
      paddingLeft: 46,
      paddingRight: 40,
    });
  });
});

describe('mobileTabBarLayout', () => {
  it('grows the tab bar around Android navigation controls', () => {
    expect(mobileTabBarLayout(20)).toEqual({
      height: 76,
      paddingTop: 6,
      paddingBottom: 12,
    });
  });
});
