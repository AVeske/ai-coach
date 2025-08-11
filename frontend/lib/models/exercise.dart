enum ExerciseGroup { chest, back, arms, legs }

class Exercise {
  final String id;
  final ExerciseGroup group;
  final String name;
  const Exercise({required this.id, required this.group, required this.name});
}

// Seed data. You can append freely; UI is dynamic.
const exercises = <Exercise>[
  // Chest
  Exercise(id: 'pushup', group: ExerciseGroup.chest, name: 'Push-ups'),
  Exercise(id: 'bench_press', group: ExerciseGroup.chest, name: 'Bench Press'),
  Exercise(
    id: 'incline_bench',
    group: ExerciseGroup.chest,
    name: 'Incline Bench Press',
  ),

  // Back
  Exercise(id: 'pull_ups', group: ExerciseGroup.back, name: 'Pull-ups'),
  Exercise(
    id: 'bent_over_rows',
    group: ExerciseGroup.back,
    name: 'Bent-over Rows',
  ),
  Exercise(
    id: 'lat_pulldown',
    group: ExerciseGroup.back,
    name: 'Lat Pulldowns',
  ),

  // Arms
  Exercise(
    id: 'standing_curl',
    group: ExerciseGroup.arms,
    name: 'Standing Bicep Curls',
  ),
  Exercise(
    id: 'tricep_extensions',
    group: ExerciseGroup.arms,
    name: 'Tricep Extensions',
  ),
  Exercise(
    id: 'preacher_curls',
    group: ExerciseGroup.arms,
    name: 'Preacher Curls',
  ),

  // Legs
  Exercise(id: 'squats', group: ExerciseGroup.legs, name: 'Squats'),
  Exercise(
    id: 'leg_extensions',
    group: ExerciseGroup.legs,
    name: 'Leg Extensions',
  ),
  Exercise(
    id: 'hamstring_curls',
    group: ExerciseGroup.legs,
    name: 'Hamstring Curls',
  ),
];

List<Exercise> byGroup(ExerciseGroup group) =>
    exercises.where((e) => e.group == group).toList(growable: false);

String groupLabel(ExerciseGroup g) {
  switch (g) {
    case ExerciseGroup.chest:
      return 'Chest';
    case ExerciseGroup.back:
      return 'Back';
    case ExerciseGroup.arms:
      return 'Arms';
    case ExerciseGroup.legs:
      return 'Legs';
  }
}
