import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/db.dart'; // NEW

class LoginPage extends StatelessWidget {
  const LoginPage({super.key});

  Future<void> _google(BuildContext ctx) async {
    try {
      final g = await GoogleSignIn().signIn();
      if (g == null) return;
      final ga = await g.authentication;
      final cred = GoogleAuthProvider.credential(
        idToken: ga.idToken,
        accessToken: ga.accessToken,
      );
      await FirebaseAuth.instance.signInWithCredential(cred);
      await Db.createProfileIfMissing(); // NEW: create/patch user doc
    } catch (e) {
      if (ctx.mounted) {
        ScaffoldMessenger.of(
          ctx,
        ).showSnackBar(SnackBar(content: Text('Sign-in failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: Center(
        child: ElevatedButton.icon(
          onPressed: () => _google(context),
          icon: const Icon(Icons.login),
          label: const Text('Sign in with Google'),
        ),
      ),
    );
  }
}
