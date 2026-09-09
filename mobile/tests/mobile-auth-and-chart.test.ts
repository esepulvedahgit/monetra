import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const mobileRoot = resolve(import.meta.dirname, '..');

function source(path: string) {
  return readFileSync(resolve(mobileRoot, path), 'utf8');
}

describe('mobile chart and sign-in controls', () => {
  it('keeps the donut center clear so category arcs remain legible', () => {
    const chart = source('src/components/FinanceUi.tsx');
    const donut = chart.slice(chart.indexOf('export function DonutChart'), chart.indexOf('export function PrimaryButton'));

    expect(donut).not.toContain('SvgText');
    expect(donut).not.toContain('compactAmount');
  });

  it('lets a person show or hide their password before signing in', () => {
    const login = source('app/(auth)/login.tsx');

    expect(login).toContain("const [passwordVisible, setPasswordVisible] = useState(false)");
    expect(login).toContain('secureTextEntry={!passwordVisible}');
    expect(login).toContain('accessibilityLabel={passwordVisible ? \'Ocultar contraseña\' : \'Mostrar contraseña\'}');
  });
});
