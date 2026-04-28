class ApiConfig {
  // Cambia esta URL al host real en producción
  static const String baseUrl = 'http://10.0.2.2:8000/api/v1';

  // Emulador Android usa 10.0.2.2 para alcanzar localhost del PC
  // Dispositivo físico: usa la IP de tu PC en la red local (ej. http://192.168.1.X:8000/api/v1)
}
