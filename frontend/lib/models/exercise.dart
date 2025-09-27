enum ExerciseGroup { chest, back, arms, legs }

class Exercise {
  final String id;
  final ExerciseGroup group;
  final String name;
  final String tip;
  const Exercise({
    required this.id,
    required this.group,
    required this.name,
    this.tip = "",
  });
}

// Seed data. You can append freely; UI is dynamic.
const exercises = <Exercise>[
  Exercise(
    id: 'pushup',
    group: ExerciseGroup.chest,
    name: 'Push-ups',
    tip: 'Side view at chest height.',
  ),
  Exercise(
    id: 'bench_press',
    group: ExerciseGroup.chest,
    name: 'Bench Press',
    tip: 'Side view from bench height.',
  ),
  Exercise(
    id: 'incline_bench',
    group: ExerciseGroup.chest,
    name: 'Incline Bench Press',
    tip: 'Side view from bench height.',
  ),

  Exercise(
    id: 'pull_ups',
    group: ExerciseGroup.back,
    name: 'Pull-ups',
    tip: 'Side view near the bar.',
  ),
  Exercise(
    id: 'bent_over_rows',
    group: ExerciseGroup.back,
    name: 'Bent-over Rows',
    tip: 'Side view at torso height.',
  ),
  Exercise(
    id: 'lat_pulldown',
    group: ExerciseGroup.back,
    name: 'Lat Pulldowns',
    tip: '45° front-side or side.',
  ),

  Exercise(
    id: 'standing_curl',
    group: ExerciseGroup.arms,
    name: 'Standing Bicep Curls',
    tip: 'Side view on working arm.',
  ),
  Exercise(
    id: 'tricep_extensions',
    group: ExerciseGroup.arms,
    name: 'Tricep Extensions',
    tip: 'Side view, elbow clearly visible.',
  ),
  Exercise(
    id: 'preacher_curls',
    group: ExerciseGroup.arms,
    name: 'Preacher Curls',
    tip: 'Side view on working arm.',
  ),

  Exercise(
    id: 'squat',
    group: ExerciseGroup.legs,
    name: 'Squats',
    tip: 'Side view at hip height.',
  ),
  Exercise(
    id: 'leg_extensions',
    group: ExerciseGroup.legs,
    name: 'Leg Extensions',
    tip: 'Side view on the moving leg.',
  ),
  Exercise(
    id: 'hamstring_curls',
    group: ExerciseGroup.legs,
    name: 'Hamstring Curls',
    tip: 'Side view on the moving leg.',
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
