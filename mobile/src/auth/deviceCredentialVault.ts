import { NativeModules, Platform } from 'react-native';

export type DeviceCredentialVaultStatus = {
  supported: boolean;
  enrolled: boolean;
  quickAccessStatusToken: string | null;
};

type NativeDeviceCredentialVault = {
  getStatus: () => Promise<DeviceCredentialVaultStatus>;
  enroll: (refreshToken: string, quickAccessStatusToken?: string | null) => Promise<void>;
  unlock: () => Promise<string>;
  rotate: (refreshToken: string, quickAccessStatusToken?: string | null) => Promise<void>;
  lock: () => Promise<void>;
  clear: () => Promise<void>;
};

const unavailable: NativeDeviceCredentialVault = {
  getStatus: async () => ({ supported: false, enrolled: false, quickAccessStatusToken: null }),
  enroll: async () => { throw new Error('El acceso rápido solo está disponible en Android 11 o superior.'); },
  unlock: async () => { throw new Error('El acceso rápido no está disponible en este dispositivo.'); },
  rotate: async () => { throw new Error('El acceso rápido no está disponible en este dispositivo.'); },
  lock: async () => undefined,
  clear: async () => undefined,
};

function nativeVault(): NativeDeviceCredentialVault {
  if (Platform.OS !== 'android') return unavailable;
  return (NativeModules.DeviceCredentialVault as NativeDeviceCredentialVault | undefined) ?? unavailable;
}

export const getDeviceCredentialVaultStatus = () => nativeVault().getStatus();
export const enrollDeviceCredentialVault = (refreshToken: string, quickAccessStatusToken?: string) => nativeVault().enroll(refreshToken, quickAccessStatusToken ?? null);
export const unlockDeviceCredentialVault = () => nativeVault().unlock();
export const rotateDeviceCredentialVault = (refreshToken: string, quickAccessStatusToken?: string) => nativeVault().rotate(refreshToken, quickAccessStatusToken ?? null);
export const lockDeviceCredentialVault = () => nativeVault().lock();
export const clearDeviceCredentialVault = () => nativeVault().clear();
