import 'package:flutter/material.dart';
import '../models/exercise.dart';
import '../widgets/exercise_tile.dart';
import 'video_upload_page.dart';

class ExerciseListPage extends StatefulWidget {
  final ExerciseGroup group;
  const ExerciseListPage({super.key, required this.group});

  @override
  State<ExerciseListPage> createState() => _ExerciseListPageState();
}

class _ExerciseListPageState extends State<ExerciseListPage> {
  String _query = '';

  void _openExercise(Exercise ex) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoUploadPage(
          exerciseId: ex.id, // <-- slug like "pushup"
          exerciseLabel: ex.name, // <-- pretty label, e.g. "Push-ups"
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final all = byGroup(widget.group);
    final visible = all
        .where((e) => e.name.toLowerCase().contains(_query.toLowerCase()))
        .toList(growable: false);

    return Scaffold(
      appBar: AppBar(title: Text(groupLabel(widget.group))),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              TextField(
                decoration: const InputDecoration(
                  hintText: 'Search exercises',
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (v) => setState(() => _query = v),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: ListView.separated(
                  itemCount: visible.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (_, i) => ExerciseTile(
                    title: visible[i].name,
                    onTap: () => _openExercise(visible[i]),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
