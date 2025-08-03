import 'package:flutter/material.dart';
import 'video_upload_page.dart';

class ChestPage extends StatelessWidget {
  const ChestPage({super.key});

  void navigateToUpload(BuildContext context, String exercise) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => VideoUploadPage(exercise: exercise)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Chest Exercises')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Pick an exercise',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 30),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Pushups'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Pushups'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Bench Press'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Bench Press'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Incline Bench Press'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Incline Bench Press'),
            ),
          ],
        ),
      ),
    );
  }
}
