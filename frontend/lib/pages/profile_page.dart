import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});
  @override
  Widget build(BuildContext context) {
    final u = FirebaseAuth.instance.currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: u == null
            ? const Text('Not signed in.')
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Email: ${u.email ?? "-"}'),
                  const SizedBox(height: 8),
                  Text('Name: ${u.displayName ?? "-"}'),
                  const SizedBox(height: 8),
                  Text('UID: ${u.uid}'),
                ],
              ),
      ),
    );
  }
}
