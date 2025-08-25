import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'theme.dart';
import 'pages/login_page.dart';
import 'pages/home_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(); // uses google-services.json
  runApp(const AICoachApp());
}

class AICoachApp extends StatefulWidget {
  const AICoachApp({super.key});
  @override
  State<AICoachApp> createState() => _AICoachAppState();
}

class _AICoachAppState extends State<AICoachApp> {
  ThemeMode _mode = ThemeMode.system;

  void _setTheme(ThemeMode m) => setState(() => _mode = m);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Coach',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: _mode,
      home: StreamBuilder<User?>(
        stream: FirebaseAuth.instance.authStateChanges(),
        builder: (_, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          return snap.data == null
              ? const LoginPage()
              : HomePage(currentMode: _mode, onChangeTheme: _setTheme);
        },
      ),
    );
  }
}
