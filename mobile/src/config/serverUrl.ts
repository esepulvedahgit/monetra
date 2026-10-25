const apiPath = '/api/v1';
const hostPattern = /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*|\[[0-9a-f:.]+\])(?::\d{1,5})?$/i;

export class ServerUrlError extends Error {}

/**
 * Turns what a person types ("monetra.example.com", "https://example.com/monetra/")
 * into the API base URL ("https://monetra.example.com/api/v1"). Only HTTPS is
 * accepted outside development builds.
 */
export function normalizeServerUrl(input: string, { allowHttp = false }: { allowHttp?: boolean } = {}): string {
  const trimmed = input.trim();
  if (!trimmed) throw new ServerUrlError('Ingresa la dirección de tu servidor Monetra.');
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  const match = /^([a-z][a-z0-9+.-]*):\/\/([^/?#]*)([^?#]*)([?#].*)?$/i.exec(withScheme);
  if (!match) throw new ServerUrlError('La dirección del servidor no es válida.');
  const [, rawScheme = '', authority = '', rawPath = '', suffix] = match;
  const scheme = rawScheme.toLowerCase();
  if (scheme !== 'https' && !(scheme === 'http' && allowHttp)) {
    throw new ServerUrlError('El servidor debe usar una dirección segura https://.');
  }
  if (authority.includes('@')) throw new ServerUrlError('La dirección no debe incluir usuario ni contraseña.');
  if (!hostPattern.test(authority)) throw new ServerUrlError('La dirección del servidor no es válida.');
  if (suffix) throw new ServerUrlError('La dirección no debe incluir parámetros (? o #).');
  const port = /:(\d+)$/.exec(authority)?.[1];
  if (port && (Number(port) < 1 || Number(port) > 65535)) throw new ServerUrlError('El puerto del servidor no es válido.');
  let path = rawPath.replace(/\/+$/, '');
  if (!path.toLowerCase().endsWith(apiPath)) path = `${path}${apiPath}`;
  return `${scheme}://${authority.toLowerCase()}${path}`;
}

/** Short, human-readable server name for the UI ("monetra.example.com"). */
export function serverLabel(serverUrl: string): string {
  return serverUrl.replace(/^[a-z]+:\/\//i, '').replace(/\/api\/v1$/i, '');
}

/** The editable form of a stored API base URL. */
export function serverInputValue(serverUrl: string): string {
  return serverUrl.replace(/\/api\/v1$/i, '');
}

type ProbeFailure = { code?: string; response?: unknown };

/**
 * A Monetra API answers an unauthenticated `GET /me` with a JSON 401. Anything
 * else (a web page, 404, a proxy error) means the address is not a Monetra server.
 * Returns null when the server looks valid, or the message to show.
 */
export function serverProbeProblem(result: { status: number; contentType?: string } | { error: ProbeFailure }): string | null {
  if ('error' in result) {
    const { code } = result.error;
    if (code === 'ECONNABORTED' || code === 'ETIMEDOUT') return 'El servidor tardó demasiado en responder. Revisa la dirección e inténtalo nuevamente.';
    return 'No se pudo conectar con el servidor. Revisa la dirección, tu conexión y que el certificado HTTPS sea válido.';
  }
  if (result.status === 401 && (result.contentType ?? '').toLowerCase().includes('application/json')) return null;
  return 'La dirección responde, pero no parece un servidor Monetra. Revisa la dirección.';
}
