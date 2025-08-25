import 'package:flutter/material.dart';
import '../models/exercise.dart';
import 'exercise_list_page.dart';

class ExerciseGroupsPage extends StatefulWidget {
  const ExerciseGroupsPage({super.key});
  @override
  State<ExerciseGroupsPage> createState() => _ExerciseGroupsPageState();
}

class _ExerciseGroupsPageState extends State<ExerciseGroupsPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tc = TabController(length: 4, vsync: this);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Exercises'),
        bottom: TabBar(
          controller: _tc,
          tabs: const [
            Tab(text: 'Chest'),
            Tab(text: 'Back'),
            Tab(text: 'Arms'),
            Tab(text: 'Legs'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tc,
        children: const [
          ExerciseListPage(group: ExerciseGroup.chest),
          ExerciseListPage(group: ExerciseGroup.back),
          ExerciseListPage(group: ExerciseGroup.arms),
          ExerciseListPage(group: ExerciseGroup.legs),
        ],
      ),
    );
  }
}
