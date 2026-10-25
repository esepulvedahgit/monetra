import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const mobileRoot = resolve(import.meta.dirname, '..');
const plugin = createRequire(import.meta.url)('../plugins/with-lets-encrypt-roots/index.cjs') as {
  certificateNames: () => string[];
  networkSecurityConfig: (options: { cleartextTrafficPermitted: boolean }) => string;
};

function source(path: string) {
  return readFileSync(resolve(mobileRoot, path), 'utf8');
}

describe("Let's Encrypt trust anchors", () => {
  it("bundles the official roots, including ISRG Root X2 for Android versions before 14", () => {
    expect(plugin.certificateNames()).toEqual(['isrg_root_x1', 'isrg_root_x2', 'isrg_root_ye', 'isrg_root_yr']);
  });

  it('keeps system roots trusted and forbids cleartext in release builds', () => {
    const config = plugin.networkSecurityConfig({ cleartextTrafficPermitted: false });
    expect(config).toContain('<certificates src="system" />');
    expect(config).toContain('<certificates src="@raw/isrg_root_x2" />');
    expect(config).toContain('cleartextTrafficPermitted="false"');
  });

  it('is registered as a config plugin so prebuild regenerates it', () => {
    expect(JSON.parse(source('app.json')).expo.plugins).toContain('./plugins/with-lets-encrypt-roots/index.cjs');
  });

  it('matches what the plugin generates in the committed Android project', () => {
    expect(source('android/app/src/main/AndroidManifest.xml')).toContain('android:networkSecurityConfig="@xml/network_security_config"');
    expect(source('android/app/src/main/res/xml/network_security_config.xml')).toBe(plugin.networkSecurityConfig({ cleartextTrafficPermitted: false }));
    for (const variant of ['debug', 'debugOptimized']) {
      expect(source(`android/app/src/${variant}/res/xml/network_security_config.xml`)).toBe(plugin.networkSecurityConfig({ cleartextTrafficPermitted: true }));
    }
    for (const name of plugin.certificateNames()) {
      expect(source(`android/app/src/main/res/raw/${name}.pem`)).toBe(source(`plugins/with-lets-encrypt-roots/certs/${name}.pem`));
    }
  });
});
