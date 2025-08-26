import 'package:flutter/material.dart';
import '../models/exercise.dart';
import '../widgets/exercise_tile.dart';
import 'exercise_wiki_detail_page.dart';

class WikiPage extends StatefulWidget {
  const WikiPage({super.key});

  @override
  State<WikiPage> createState() => _WikiPageState();
}

class _WikiPageState extends State<WikiPage> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final visible = exercises
        .where((e) => e.name.toLowerCase().contains(_query.toLowerCase()))
        .toList(growable: false);

    return Scaffold(
      appBar: AppBar(title: const Text('Exercise Wiki')),
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
                    final ex = visible[i];
                    return ExerciseTile(
                      title: ex.name,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                ExerciseWikiDetailPage(exercise: ex),
                          ),
                        );
                      },
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
