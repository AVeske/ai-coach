import 'package:flutter/material.dart';
import '../models/exercise.dart';
import 'exercise_list_page.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  void _openGroup(BuildContext context, ExerciseGroup group) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => ExerciseListPage(group: group)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = ExerciseGroup.values;
    return Scaffold(
      appBar: AppBar(title: const Text('AI Coach')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Select a body part',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: GridView.builder(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    childAspectRatio: 1.15,
                  ),
                  itemCount: groups.length,
                  itemBuilder: (_, i) {
                    final g = groups[i];
                    return _GroupCard(
                      title: groupLabel(g),
                      onTap: () => _openGroup(context, g),
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

class _GroupCard extends StatelessWidget {
  final String title;
  final VoidCallback onTap;
  const _GroupCard({required this.title, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Ink(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            colors: [Color(0xFF9C6410), Color(0xFF744B0D)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          border: Border.all(color: Color(0xFF70542A)),
        ),
        child: Center(
          child: Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
        ),
      ),
    );
  }
}
