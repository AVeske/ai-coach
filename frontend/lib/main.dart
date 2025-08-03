import 'package:flutter/material.dart';
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
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}
