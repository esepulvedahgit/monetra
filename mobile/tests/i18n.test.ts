import { describe, expect, it } from 'vitest';

import { createI18n } from '../src/i18n';

describe('mobile translations', () => {
  it('provides the bottom navigation in Spanish by default', async () => {
    const i18n = createI18n();
    await i18n.changeLanguage('es');

    expect(i18n.t('tabs.summary')).toBe('Resumen');
  });

  it('provides the bottom navigation in English', async () => {
    const i18n = createI18n();
    await i18n.changeLanguage('en');

    expect(i18n.t('tabs.transactions')).toBe('Transactions');
  });
});
