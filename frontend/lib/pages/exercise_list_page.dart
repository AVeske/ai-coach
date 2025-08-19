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
      MaterialPageRoute(builder: (_) => VideoUploadPage(exercise: ex.id)),
    );
  }

  void _showTip(Exercise ex) {
    final tip = ex.tip.isEmpty
        ? 'Use a steady side view with good lighting.'
        : ex.tip;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Filming tip'),
        content: Text(tip),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
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
                  itemBuilder: (_, i) {
                    final e = visible[i];
                    return ExerciseTile(
                      title: e.name,
                      onTap: () => _openExercise(e),
                      onInfo: () => _showTip(e), // NEW
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
