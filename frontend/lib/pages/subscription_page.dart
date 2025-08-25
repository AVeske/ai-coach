import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class SubscriptionPage extends StatelessWidget {
  const SubscriptionPage({super.key});

  @override
  Widget build(BuildContext context) {
    final uid = FirebaseAuth.instance.currentUser!.uid;
    final doc = FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .snapshots();

    return Scaffold(
      appBar: AppBar(title: const Text('Subscription')),
      body: StreamBuilder<DocumentSnapshot<Map<String, dynamic>>>(
        stream: doc,
        builder: (_, s) {
          if (!s.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final d = s.data!.data() ?? {};
          final tier = (d['tier'] ?? 0).toString();
          final status = (d['sub_status'] ?? 'none').toString();
          final expiry = (d['tier_expiry'] != null)
              ? d['tier_expiry'].toDate().toString().split('.').first
              : '—';

          return Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Tier: $tier',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text('Status: $status'),
                const SizedBox(height: 4),
                Text('Expires: $expiry'),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () =>
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Checkout coming soon'),
                              ),
                            ),
                        icon: const Icon(Icons.upgrade),
                        label: const Text('Upgrade'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () =>
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Portal coming soon'),
                              ),
                            ),
                        icon: const Icon(Icons.manage_accounts),
                        label: const Text('Manage/Cancel'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                const Text('Placeholder. Stripe wiring later.'),
              ],
            ),
          );
        },
      ),
    );
  }
}
