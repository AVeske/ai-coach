import 'package:flutter/material.dart';
import 'chest_page.dart';
import 'back_page.dart';
import 'arms_page.dart';
import 'legs_page.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  void navigateTo(BuildContext context, Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Coach 💪')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center, // center vertically
            crossAxisAlignment:
                CrossAxisAlignment.stretch, // full width buttons
            children: [
              const Text(
                'Ready to get shredded?',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 40),
              ElevatedButton(
                onPressed: () => navigateTo(context, const ChestPage()),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  textStyle: const TextStyle(fontSize: 20),
                ),
                child: const Text('Chest'),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => navigateTo(context, const BackPage()),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  textStyle: const TextStyle(fontSize: 20),
                ),
                child: const Text('Back'),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => navigateTo(context, const ArmsPage()),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  textStyle: const TextStyle(fontSize: 20),
                ),
                child: const Text('Arms'),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => navigateTo(context, const LegsPage()),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  textStyle: const TextStyle(fontSize: 20),
                ),
                child: const Text('Legs'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
