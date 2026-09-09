import { clearTokens, getTokens, setTokens, type Tokens } from './tokens';
import { SessionTokenOwner } from './tokenOwner';

const tokenOwner = new SessionTokenOwner<Tokens>({ get: getTokens, set: setTokens, clear: clearTokens });

export const beginTokenSession = () => tokenOwner.begin();
export const currentTokenSession = () => tokenOwner.current();
export const isCurrentTokenSession = (session: number) => tokenOwner.isCurrent(session);
export const getSessionTokens = () => tokenOwner.get();
export const setSessionTokens = (session: number, tokens: Tokens) => tokenOwner.set(session, tokens);
export const clearSessionTokens = (session: number) => tokenOwner.clear(session);
