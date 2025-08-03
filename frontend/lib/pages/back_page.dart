import 'package:flutter/material.dart';
import 'video_upload_page.dart';

class BackPage extends StatelessWidget {
  const BackPage({super.key});

  void navigateToUpload(BuildContext context, String exercise) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => VideoUploadPage(exercise: exercise)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Back Exercises')),
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
              onPressed: () => navigateToUpload(context, 'Pull-ups'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Pull-ups'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Bent-over Rows'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Bent-over Rows'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => navigateToUpload(context, 'Lat Pulldowns'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18),
              ),
              child: const Text('Lat Pulldowns'),
            ),
          ],
        ),
      ),
    );
  }
}
