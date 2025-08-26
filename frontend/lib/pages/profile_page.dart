import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import '../services/db.dart';
import 'profile_setup_page.dart';
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
        stream: Db.userDoc(u.uid).snapshots(),
        builder: (_, snap) {
          if (!snap.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final d = snap.data!.data() ?? {};
          final sub = (d['subscription'] as Map?) ?? {};
          return Padding(
            padding: const EdgeInsets.all(16),
            child: ListView(
              children: [
                _row('Email', u.email ?? '-'),
                _row('Name', u.displayName ?? '-'),
                _row('Country', (d['country'] ?? '-').toString()),
                _row('Gym', (d['gymName'] ?? '-').toString()),
                _row('Experience', (d['experienceLevel'] ?? '-').toString()),
                _row('Favorite group', (d['favoriteGroup'] ?? '-').toString()),
                _row('Plan', (sub['plan'] ?? 'free').toString()),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => ProfileSetupPage(onDone: () {}),
                      ),
                    );
                  },
                  icon: const Icon(Icons.edit),
                  label: const Text('Edit profile'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const CalibrationIntroPage(),
                      ),
                    );
                  },
                  icon: const Icon(Icons.straighten),
                  label: const Text('Calibration'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _row(String k, String v) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 140,
            child: Text(
              '$k:',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(child: Text(v)),
        ],
      ),
    );
  }
}
