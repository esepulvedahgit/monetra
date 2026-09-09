import type { EdgeInsets } from 'react-native-safe-area-context';

import { spacing } from '../theme/tokens';

export function mobileContentInsets(insets: EdgeInsets) {
  return {
    paddingTop: insets.top,
    paddingBottom: insets.bottom + spacing.xl,
    paddingLeft: insets.left + spacing.md,
    paddingRight: insets.right + spacing.md,
  };
}

export function mobileTabBarLayout(bottomInset: number) {
  return {
    height: 56 + bottomInset,
    paddingTop: 6,
    paddingBottom: Math.max(6, bottomInset - spacing.sm),
  };
}
