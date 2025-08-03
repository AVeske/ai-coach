import 'package:flutter/material.dart';
import 'legs_exercise_page.dart';

class LegsPage extends StatefulWidget {
  const LegsPage({super.key});

  @override
  State<LegsPage> createState() => _LegsPageState();
}

class _LegsPageState extends State<LegsPage> {
  bool agreed = false;

  void goToExercises(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const LegsExercisePage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Legs 😬')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'Really?? You actually going to train legs?',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 40),
            CheckboxListTile(
              title: const Text('I have chicken legs 🐔'),
              value: agreed,
              onChanged: (value) {
                setState(() {
                  agreed = value ?? false;
                });
              },
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: agreed ? () => goToExercises(context) : null,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  vertical: 16,
                  horizontal: 24,
                ),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text("I Agree, let's train"),
            ),
          ],
        ),
      ),
    );
  }
}
