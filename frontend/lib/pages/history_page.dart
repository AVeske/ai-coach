import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import '../services/db.dart';

class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('History')),
      body: StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
        stream: Db.streamMySessions(),
        builder: (_, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final docs = snap.data?.docs ?? [];
          if (docs.isEmpty) {
            return const Center(child: Text('No sessions yet.'));
          }

          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: docs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final d = docs[i].data();

              final ts = d['createdAt'] as Timestamp?;
              final date = ts?.toDate();

              final ex = (d['exerciseId'] ?? '-').toString();

              int asInt(dynamic v) => v is int ? v : int.tryParse('$v') ?? 0;
              final reps = asInt(d['repsCount']);
              final good = asInt(d['goodReps']);
              final bad = asInt(d['badReps']);

              final summary = (d['feedbackSummary'] ?? '').toString();
              final full = (d['feedbackFull'] ?? '').toString();

              String weightStr = '';
              final w = d['weight'];
              if (w is Map) {
                final val = w['value'];
                final unit = (w['unit'] ?? '').toString();
                if (val != null) {
                  final numVal = (val is num) ? val : num.tryParse('$val');
                  if (numVal != null) {
                    weightStr =
                        ' • Weight: ${numVal.toString()}${unit.isNotEmpty ? ' $unit' : ''}';
                  }
                }
              }

              final subtitleLines = <String>[
                if (date != null) date.toLocal().toString(),
                'Reps: $reps  •  Good: $good  •  Needs work: $bad$weightStr',
                if (summary.isNotEmpty) summary,
              ];

              return ExpansionTile(
                shape: RoundedRectangleBorder(
                  side: BorderSide(color: Theme.of(context).dividerColor),
                  borderRadius: BorderRadius.circular(12),
                ),
                collapsedShape: RoundedRectangleBorder(
                  side: BorderSide(color: Theme.of(context).dividerColor),
                  borderRadius: BorderRadius.circular(12),
                ),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                tilePadding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                title: Text(
                  ex,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                subtitle: Text(
                  subtitleLines.where((s) => s.isNotEmpty).join('\n'),
                ),
                children: [
                  if (full.isNotEmpty)
                    Text(full, style: const TextStyle(height: 1.3)),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
