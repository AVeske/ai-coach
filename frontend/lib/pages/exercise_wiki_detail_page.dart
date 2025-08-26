import 'package:flutter/material.dart';
import '../models/exercise.dart';

class ExerciseWikiDetailPage extends StatelessWidget {
  final Exercise exercise;
  const ExerciseWikiDetailPage({super.key, required this.exercise});

  @override
  Widget build(BuildContext context) {
    final entry = _WIKI[exercise.id] ?? _WIKI['__default__']!;
    return Scaffold(
      appBar: AppBar(title: Text(exercise.name)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (exercise.tip.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF3E0),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFFFCC80)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline),
                    const SizedBox(width: 8),
                    Expanded(child: Text(exercise.tip)),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
            Text(
              'Overview',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(entry.description),
            const SizedBox(height: 16),
            Text(
              'How to do it',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            ...entry.steps.map(
              (s) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• '),
                    Expanded(child: Text(s)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Reference positions (coming soon)',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(child: _placeholderCard('Top position')),
                const SizedBox(width: 12),
                Expanded(child: _placeholderCard('Bottom position')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _placeholderCard(String label) {
    return Container(
      height: 140,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFDDDDDD)),
        color: const Color(0xFFF7F7F7),
      ),
      child: Center(
        child: Text(label, style: const TextStyle(color: Colors.black54)),
      ),
    );
  }
}

/// Simple local content model + data. We can move this to Firestore later.
class _WikiEntry {
  final String description;
  final List<String> steps;
  const _WikiEntry({required this.description, required this.steps});
}

const Map<String, _WikiEntry> _WIKI = {
  '__default__': _WikiEntry(
    description:
        'Basic exercise instructions. Stand tall, control the range of motion, and use a weight you can manage with good form.',
    steps: [
      'Set up safely and choose an appropriate load.',
      'Move through a full, controlled range of motion.',
      'Keep a neutral spine and steady breathing.',
      'Stop the set when form breaks down.',
    ],
  ),

  // Chest
  'pushup': _WikiEntry(
    description:
        'A bodyweight horizontal press emphasizing chest, triceps, and front delts.',
    steps: [
      'Hands under shoulders, body in a straight line.',
      'Lower chest toward the floor without flaring elbows excessively.',
      'Keep core and glutes tight; no hip sagging.',
      'Press back to full lockout with control.',
    ],
  ),
  'bench_press': _WikiEntry(
    description:
        'Barbell press from a bench targeting chest, triceps, and anterior delts.',
    steps: [
      'Feet planted, slight arch, shoulders retracted.',
      'Lower bar to mid-chest with forearms vertical.',
      'Touch lightly—don’t bounce.',
      'Press up to full elbow extension; keep shoulder blades set.',
    ],
  ),
  'incline_bench': _WikiEntry(
    description:
        'Bench press on an incline to bias upper chest and front delts.',
    steps: [
      'Set bench 25–45° incline.',
      'Lower to upper-chest/clavicle line.',
      'Drive up while keeping elbows at ~45–60°.',
      'Control tempo; avoid shrugging.',
    ],
  ),

  // Back
  'pull_ups': _WikiEntry(
    description: 'Vertical pull for lats and upper back using bodyweight.',
    steps: [
      'Grip the bar slightly wider than shoulder width.',
      'Start from a dead hang; engage lats first.',
      'Pull chest toward bar without swinging.',
      'Lower under control to full hang.',
    ],
  ),
  'bent_over_rows': _WikiEntry(
    description:
        'Hip-hinged horizontal row strengthening lats, mid-back, and posterior chain.',
    steps: [
      'Hinge at hips, neutral spine, bar over mid-foot.',
      'Row toward lower ribs/upper abs.',
      'Keep elbows close; no torso jerking.',
      'Lower slow; maintain back angle.',
    ],
  ),
  'lat_pulldown': _WikiEntry(
    description:
        'Machine variation of the vertical pull emphasizing lat engagement.',
    steps: [
      'Set pad snug on thighs; grip just wider than shoulders.',
      'Pull bar to upper chest while keeping chest up.',
      'Avoid leaning back excessively.',
      'Control return to full stretch.',
    ],
  ),

  // Arms
  'standing_curl': _WikiEntry(
    description: 'Biceps isolation with barbell or dumbbells.',
    steps: [
      'Stand tall, elbows close to torso.',
      'Curl without swinging; control the negative.',
      'Squeeze at the top; don’t let shoulders roll forward.',
      'Full elbow extension at the bottom.',
    ],
  ),
  'tricep_extensions': _WikiEntry(
    description: 'Isolation for triceps (overhead cable/dumbbell or rope).',
    steps: [
      'Elbows stay narrow and stacked over shoulders.',
      'Lower with control; feel stretch on long head.',
      'Extend to full lockout without flaring.',
      'Keep ribs down; avoid over-arching.',
    ],
  ),
  'preacher_curls': _WikiEntry(
    description: 'Biceps curl using preacher bench to reduce cheating.',
    steps: [
      'Upper arm fixed on the pad.',
      'Curl through full range; pause near top.',
      'Lower slowly to near full extension.',
      'Pick a load that allows control.',
    ],
  ),

  // Legs
  'squats': _WikiEntry(
    description: 'Compound lower-body lift for quads, glutes, and core.',
    steps: [
      'Feet about shoulder width; brace core.',
      'Sit hips back/down; knees track over toes.',
      'Depth to at least thighs parallel (as mobility allows).',
      'Drive up keeping chest proud and spine neutral.',
    ],
  ),
  'leg_extensions': _WikiEntry(
    description: 'Quad isolation on machine.',
    steps: [
      'Pad sits above ankles; align knee with machine pivot.',
      'Extend to squeeze quads; don’t slam pad.',
      'Lower under control to a comfortable stretch.',
      'Keep hips glued to the seat.',
    ],
  ),
  'hamstring_curls': _WikiEntry(
    description: 'Hamstring isolation (lying or seated curl).',
    steps: [
      'Align knee with the machine’s axis.',
      'Curl pad toward glutes without hip lift.',
      'Squeeze briefly; lower with control.',
      'Avoid excessive lumbar extension.',
    ],
  ),
};
