import 'package:flutter/material.dart';
import 'video_upload_page.dart';

class ArmsPage extends StatelessWidget {
  const ArmsPage({super.key});

  void navigateToUpload(BuildContext context, String exercise) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => VideoUploadPage(exercise: exercise)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Arm Exercises')),
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
              onPressed: () =>
                  navigateToUpload(context, 'Standing Bicep Curls'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Standing Bicep Curls'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Tricep Extensions'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Tricep Extensions'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Preacher Curls'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Preacher Curls'),
            ),
          ],
        ),
      ),
    );
  }
}
