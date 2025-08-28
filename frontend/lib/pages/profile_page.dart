import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import '../services/db.dart';
import 'profile_edit_page.dart';
import 'calibration_intro_page.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    final u = FirebaseAuth.instance.currentUser;
    if (u == null) {
      return const Scaffold(body: Center(child: Text('Not signed in.')));
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: StreamBuilder<DocumentSnapshot<Map<String, dynamic>>>(
        stream: Db.streamUserDoc(),
        builder: (_, snap) {
          if (!snap.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snap.data!.data() ?? {};
          final subscription = (data['subscription'] as Map?) ?? {};
          final plan = (subscription['plan'] ?? 'free').toString();

          final country = (data['country'] ?? '-').toString();
          final gymName = (data['gymName'] ?? '-').toString();
          final level = (data['experienceLevel'] ?? '-').toString();
          final fav = (data['favoriteGroup'] ?? '-').toString();

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Identity block
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Theme.of(context).dividerColor),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        u.displayName ?? u.email ?? '-',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(u.email ?? '-', style: const TextStyle(height: 1.2)),
                      const SizedBox(height: 6),
                      Text('Plan: ${plan.toUpperCase()}'),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),

              // Read-only training prefs
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Theme.of(context).dividerColor),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _roRow('Country', country),
                      _roRow('Gym name', gymName),
                      _roRow('Experience level', level),
                      _roRow('Favorite group', fav),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerRight,
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.edit_outlined),
                          label: const Text('Edit'),
                          onPressed: () async {
                            await Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => ProfileEditPage(
                                  initialCountry: country == '-'
                                      ? null
                                      : country,
                                  initialGymName: gymName == '-'
                                      ? null
                                      : gymName,
                                  initialLevel: level == '-' ? null : level,
                                  initialFavGroup: fav == '-' ? null : fav,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),

              // Calibration
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Theme.of(context).dividerColor),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text('Calibration'),
                        subtitle: Text(
                          'Add (or re-do) optional photos for body-length calibration. '
                          'We store only derived measurements — not your photos.',
                        ),
                      ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: FilledButton.icon(
                          icon: const Icon(Icons.camera_alt_outlined),
                          label: const Text('Open calibration'),
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => const CalibrationIntroPage(),
                              ),
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _roRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(width: 140, child: Text(label)),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
