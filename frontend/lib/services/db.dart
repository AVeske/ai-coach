import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class Db {
  static final _fs = FirebaseFirestore.instance;

  static String? get _uid => FirebaseAuth.instance.currentUser?.uid;

  static DocumentReference<Map<String, dynamic>> userDoc(String uid) =>
      _fs.collection('users').doc(uid);

  static Stream<DocumentSnapshot<Map<String, dynamic>>> streamUserDoc() {
    final u = FirebaseAuth.instance.currentUser;
    if (u == null) return const Stream.empty();
    return userDoc(u.uid).snapshots();
  }

  /// Create/patch user on first login; keep onboarded=false until profile is saved.
  /// Also removes legacy `subscriptionTier` and ensures `subscription.plan`.
  static Future<void> createProfileIfMissing() async {
    final u = FirebaseAuth.instance.currentUser;
    if (u == null) return;
    final ref = userDoc(u.uid);
    await _fs.runTransaction((tx) async {
      final snap = await tx.get(ref);
      final now = FieldValue.serverTimestamp();
      if (!snap.exists) {
        tx.set(ref, {
          'email': u.email,
          'displayName': u.displayName,
          'photoURL': u.photoURL,
          'providerIds': u.providerData.map((p) => p.providerId).toList(),
          'createdAt': now,
          'lastLoginAt': now,
          'updatedAt': now,
          'onboarded': false, // <-- important
          'subscription': {'plan': 'free'},
        });
      } else {
        tx.update(ref, {
          'lastLoginAt': now,
          'updatedAt': now,
          'providerIds': FieldValue.arrayUnion(
            u.providerData.map((p) => p.providerId).toList(),
          ),
        });
        final data = snap.data();
        if (data != null) {
          if (data.containsKey('subscriptionTier')) {
            tx.update(ref, {'subscriptionTier': FieldValue.delete()});
          }
          final sub = (data['subscription'] as Map?) ?? {};
          if (sub['plan'] == null) {
            tx.update(ref, {
              'subscription': {'plan': 'free'},
            });
          }
        }
      }
    });
  }

  static Future<void> setOnboardedTrue() async {
    final uid = _uid;
    if (uid == null) return;
    await userDoc(
      uid,
    ).update({'onboarded': true, 'updatedAt': FieldValue.serverTimestamp()});
  }

  static Future<void> updateUserProfile({
    String? country,
    String? gymName,
    String? experienceLevel,
    String? favoriteGroup,
  }) async {
    final uid = _uid;
    if (uid == null) return;
    final data = <String, dynamic>{};
    if (country != null) data['country'] = country;
    if (gymName != null) data['gymName'] = gymName;
    if (experienceLevel != null) data['experienceLevel'] = experienceLevel;
    if (favoriteGroup != null) data['favoriteGroup'] = favoriteGroup;
    if (data.isEmpty) return;
    data['updatedAt'] = FieldValue.serverTimestamp();
    await userDoc(uid).set(data, SetOptions(merge: true));
  }

  /// Record calibration state on the user doc (root-level `calibration` map).
  static Future<void> setCalibrationStatus({
    required bool completed,
    required String method, // 'skipped' | 'uploaded' (or similar)
  }) async {
    final uid = _uid;
    if (uid == null) return;
    await userDoc(uid).set({
      'calibration': {'completed': completed, 'method': method, 'version': 1},
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));
  }

  // ------- Sessions (history) -------

  static Stream<QuerySnapshot<Map<String, dynamic>>> streamMySessions() {
    final uid = _uid;
    if (uid == null) return const Stream.empty();
    return userDoc(
      uid,
    ).collection('sessions').orderBy('createdAt', descending: true).snapshots();
  }

  static Future<void> addSession({
    required String exerciseId,
    required int repsCount,
    required int goodReps,
    required int badReps,
    required String feedbackSummary,
    required String feedbackFull,
    Map<String, dynamic>? rawMetrics,
  }) async {
    final uid = _uid;
    if (uid == null) return;
    await userDoc(uid).collection('sessions').add({
      'exerciseId': exerciseId,
      'repsCount': repsCount,
      'goodReps': goodReps,
      'badReps': badReps,
      'feedbackSummary': feedbackSummary,
      'feedbackFull': feedbackFull,
      if (rawMetrics != null) 'metrics': rawMetrics,
      'createdAt': FieldValue.serverTimestamp(),
    });
  }
}
