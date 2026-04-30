import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/auth_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => AuthProvider()..tryAutoLogin(),
      child: const MonеtraApp(),
    ),
  );
}

class MonеtraApp extends StatelessWidget {
  const MonеtraApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Monetra',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.dark(
          primary: const Color(0xFF00C896),
          secondary: const Color(0xFFF2C94C),
          surface: const Color(0xFF0B1F2A),
        ),
        scaffoldBackgroundColor: const Color(0xFF071821),
        useMaterial3: true,
      ),
      home: Consumer<AuthProvider>(
        builder: (context, auth, _) {
          if (auth.isLoading) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          return auth.isAuthenticated ? const HomeScreen() : const LoginScreen();
        },
      ),
    );
  }
}
