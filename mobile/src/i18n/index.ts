import i18next, { type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  es: {
    translation: {
      tabs: {
        summary: 'Resumen',
        transactions: 'Movimientos',
        goals: 'Metas',
        profile: 'Perfil',
      },
      auth: {
        signIn: 'Iniciar sesión',
        email: 'Correo electrónico',
        password: 'Contraseña',
        forgotPassword: 'Olvidé mi contraseña',
        verifyCode: 'Verificar código',
      },
      screens: {
        summary: 'Resumen',
        transactions: 'Movimientos',
        goals: 'Metas de ahorro',
        profile: 'Perfil',
      },
      common: {
        comingSoon: 'Esta sección se conectará a tu cuenta Monetra.',
        retry: 'Reintentar',
      },
    },
  },
  en: {
    translation: {
      tabs: {
        summary: 'Summary',
        transactions: 'Transactions',
        goals: 'Goals',
        profile: 'Profile',
      },
      auth: {
        signIn: 'Sign in',
        email: 'Email address',
        password: 'Password',
        forgotPassword: 'Forgot password',
        verifyCode: 'Verify code',
      },
      screens: {
        summary: 'Summary',
        transactions: 'Transactions',
        goals: 'Savings goals',
        profile: 'Profile',
      },
      common: {
        comingSoon: 'This section will connect to your Monetra account.',
        retry: 'Try again',
      },
    },
  },
} as const;

export function createI18n(): I18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    compatibilityJSON: 'v4',
    fallbackLng: 'es',
    lng: 'es',
    resources,
    interpolation: { escapeValue: false },
  });
  return instance;
}

export const i18n = createI18n();
