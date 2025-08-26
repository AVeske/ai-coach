import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'theme.dart';
import 'pages/login_page.dart';
import 'pages/home_page.dart';
import 'pages/profile_setup_page.dart';
import 'services/db.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(); // uses google-services files
  runApp(const AICoachApp());
}

class AICoachApp extends StatefulWidget {
  const AICoachApp({super.key});

  @override
  State<AICoachApp> createState() => _AICoachAppState();
}

class _AICoachAppState extends State<AICoachApp> {
  ThemeMode _mode = ThemeMode.system;

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
        builder: (_, authSnap) {
          final user = authSnap.data;
          if (user == null) return const LoginPage();

          // Ensure user doc and drive first-run flow
          return StreamBuilder(
            stream: Db.streamUserDoc(),
            builder: (_, docSnap) {
              if (!docSnap.hasData) {
                // Kick off creation in background (safe if exists)
                Db.createProfileIfMissing();
                return const Scaffold(
                  body: Center(child: CircularProgressIndicator()),
                );
              }
              // No cast needed; data() is already Map<String, dynamic>?
              final data = docSnap.data!.data() ?? <String, dynamic>{};
              final onboarded = (data['onboarded'] == true);

              if (!onboarded) {
                return ProfileSetupPage(
                  onDone: () {
                    setState(() {}); // rebuild into Home after setup
                  },
                );
              }

              return HomePage(
                currentMode: _mode,
                onChangeTheme: (m) => setState(() => _mode = m),
              );
            },
          );
        },
      ),
    );
  }
}
