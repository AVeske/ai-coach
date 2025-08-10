import 'package:flutter/material.dart';
import 'theme.dart';
import 'pages/home_page.dart';

void main() {
  runApp(const AICoachApp());
}

class AICoachApp extends StatelessWidget {
  const AICoachApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Coach',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: const HomePage(),
    );
  }
}
