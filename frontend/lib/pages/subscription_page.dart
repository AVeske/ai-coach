import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import '../services/db.dart';

class SubscriptionPage extends StatelessWidget {
  const SubscriptionPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Subscription')),
      body: StreamBuilder<DocumentSnapshot<Map<String, dynamic>>>(
        stream: Db.streamUserDoc(),
        builder: (_, snap) {
          final data = snap.data?.data() ?? {};
          final plan = Db.effectivePlanFrom(data); // 'free' | 'tier1' | 'tier2'
          final isPaid = plan != 'free';

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Theme.of(context).dividerColor),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                        isPaid
                            ? Icons.workspace_premium_rounded
                            : Icons.lock_open_rounded,
                        size: 28,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Current plan: ${plan.toUpperCase()}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 16,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              isPaid
                                  ? 'Thanks for supporting us! You have unlimited analyses and no ads.'
                                  : 'Free plan: limited daily analyses. Upgrade to unlock more.',
                              style: const TextStyle(height: 1.3),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12), // <-- keep buttons higher

              FilledButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Upgrades coming soon')),
                  );
                },
                icon: const Icon(Icons.upgrade_rounded),
                label: const Text('Upgrade (coming soon)'),
              ),

              if (isPaid) // <-- only visible when already subscribed
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.cancel_schedule_send_outlined),
                    label: const Text('Cancel subscription'),
                    onPressed: () async {
                      final ok = await showDialog<bool>(
                        context: context,
                        builder: (_) => AlertDialog(
                          title: const Text('Cancel subscription?'),
                          content: const Text(
                            'You will keep access until your current period ends. Continue?',
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context, false),
                              child: const Text('No'),
                            ),
                            FilledButton(
                              onPressed: () => Navigator.pop(context, true),
                              child: const Text('Yes, cancel'),
                            ),
                          ],
                        ),
                      );
                      if (ok == true) {
                        await Db.setSubscriptionPlan('free');
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Subscription set to FREE'),
                            ),
                          );
                        }
                      }
                    },
                  ),
                ),

              const SizedBox(height: 24),
              Text(
                'What you get with paid plans',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              const _Bullet('Unlimited daily analyses'),
              const _Bullet('No ads'),
              const _Bullet('Priority processing'),
              const _Bullet('Early access to new features'),
            ],
          );
        },
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  final String text;
  const _Bullet(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('•  '),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
