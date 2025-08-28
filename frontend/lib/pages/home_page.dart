import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:frontend/pages/subscription_page.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'exercise_groups_page.dart';
import 'history_page.dart';
import 'profile_page.dart';
import 'exercise_wiki_page.dart';

class HomePage extends StatelessWidget {
  final ThemeMode currentMode;
  final void Function(ThemeMode) onChangeTheme;
  const HomePage({
    super.key,
    required this.currentMode,
    required this.onChangeTheme,
  });

  Future<void> _logout(BuildContext ctx) async {
    try {
      await GoogleSignIn().signOut();
    } catch (_) {}
    await FirebaseAuth.instance.signOut();
    if (ctx.mounted) {
      ScaffoldMessenger.of(
        ctx,
      ).showSnackBar(const SnackBar(content: Text('Signed out')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Coach'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) {
              switch (v) {
                case 'light':
                  onChangeTheme(ThemeMode.light);
                  break;
                case 'dark':
                  onChangeTheme(ThemeMode.dark);
                  break;
                case 'system':
                  onChangeTheme(ThemeMode.system);
                  break;
                case 'logout':
                  _logout(context);
                  break;
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'light', child: Text('Light theme')),
              PopupMenuItem(value: 'dark', child: Text('Dark theme')),
              PopupMenuItem(value: 'system', child: Text('System theme')),
              PopupMenuDivider(),
              PopupMenuItem(value: 'logout', child: Text('Sign out')),
            ],
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: GridView.count(
          crossAxisCount: 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          children: [
            _tile(
              context,
              icon: Icons.fitness_center,
              label: 'Choose exercise',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ExerciseGroupsPage()),
              ),
            ),
            _tile(
              context,
              icon: Icons.history,
              label: 'History',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const HistoryPage()),
              ),
            ),
            _tile(
              context,
              icon: Icons.person,
              label: 'Profile',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ProfilePage()),
              ),
            ),
            _tile(
              context,
              icon: Icons.menu_book_rounded,
              label: 'Exercise Wiki',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const WikiPage()),
              ),
            ),
            _tile(
              context,
              icon: Icons.workspace_premium_rounded,
              label: 'Subscription',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SubscriptionPage()),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _tile(
    BuildContext context, {
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    final color = Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Ink(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 36, color: color),
              const SizedBox(height: 8),
              Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}
