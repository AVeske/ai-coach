import 'package:flutter/material.dart';
import '../services/db.dart';

class CalibrationIntroPage extends StatelessWidget {
  const CalibrationIntroPage({super.key});

  Future<void> _skip(BuildContext context) async {
    await Db.setCalibrationStatus(completed: true, method: 'skipped');
    if (!context.mounted) return;
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Calibration')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Text(
              'Optional: add two photos (front & side) to calibrate body lengths. '
              'You can skip now and add later from Profile.',

              style: TextStyle(height: 1.35),
            ),

            // Slight space after the intro text
            const SizedBox(height: 12),

            // Use asymmetric spacers to position buttons a bit higher
            const Spacer(flex: 2),

            // Button cluster
            FilledButton.icon(
              onPressed: () {
                // TODO: push capture page when ready
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(const SnackBar(content: Text('Coming soon')));
              },
              icon: const Icon(Icons.camera_alt),
              label: const Text('Start calibration'),
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () => _skip(context),
              child: const Text('Skip for now'),
            ),

            // More space below than above -> pushes buttons up a bit
            const Spacer(flex: 2),
          ],
        ),
      ),
    );
  }
}
