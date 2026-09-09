import { NativeModules, Platform } from 'react-native';

export type DeviceCredentialVaultStatus = {
  supported: boolean;
  enrolled: boolean;
};

type NativeDeviceCredentialVault = {
  getStatus: () => Promise<DeviceCredentialVaultStatus>;
  enroll: (refreshToken: string) => Promise<void>;
  unlock: () => Promise<string>;
  rotate: (refreshToken: string) => Promise<void>;
  lock: () => Promise<void>;
  clear: () => Promise<void>;
};

const unavailable: NativeDeviceCredentialVault = {
  getStatus: async () => ({ supported: false, enrolled: false }),
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
export const enrollDeviceCredentialVault = (refreshToken: string) => nativeVault().enroll(refreshToken);
export const unlockDeviceCredentialVault = () => nativeVault().unlock();
export const rotateDeviceCredentialVault = (refreshToken: string) => nativeVault().rotate(refreshToken);
export const lockDeviceCredentialVault = () => nativeVault().lock();
export const clearDeviceCredentialVault = () => nativeVault().clear();
