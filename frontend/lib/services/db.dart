import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class Db {
  static final _fs = FirebaseFirestore.instance;
  static final _auth = FirebaseAuth.instance;

  // ---------- Collections / Docs ----------
  static DocumentReference<Map<String, dynamic>> userDoc(String uid) =>
      _fs.collection('users').doc(uid);

  static CollectionReference<Map<String, dynamic>> sessionsCol(String uid) =>
      userDoc(uid).collection('sessions');

  // ---------- User bootstrap ----------
  static Future<void> createProfileIfMissing() async {
    final u = _auth.currentUser;
    if (u == null) return;
    final ref = userDoc(u.uid);
    final snap = await ref.get();
    if (!snap.exists) {
      await ref.set({
        'email': u.email,
        'displayName': u.displayName,
        'photoURL': u.photoURL,
        'providerIds': (u.providerData.map((e) => e.providerId).toList()),
        'createdAt': FieldValue.serverTimestamp(),
        'updatedAt': FieldValue.serverTimestamp(),
        'lastLoginAt': FieldValue.serverTimestamp(),
        'onboarded': false,
        'subscription': {
          'plan': 'free',
          // endsAt left null for free
        },
      }, SetOptions(merge: true));
    } else {
      // patch login timestamp
      await ref.set({
        'lastLoginAt': FieldValue.serverTimestamp(),
        'updatedAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));
    }
  }

  // ---------- Streams ----------
  static Stream<DocumentSnapshot<Map<String, dynamic>>> streamUserDoc() {
    final u = _auth.currentUser;
    if (u == null) {
      // return a dummy stream that never emits
      return const Stream.empty();
    }
    return userDoc(u.uid).snapshots();
  }

  static Stream<QuerySnapshot<Map<String, dynamic>>> streamMySessions() {
    final u = _auth.currentUser;
    if (u == null) return const Stream.empty();
    return sessionsCol(
      u.uid,
    ).orderBy('createdAt', descending: true).limit(200).snapshots();
  }

  /// Sessions since local midnight *client-side* (good enough for display-only).
  static Stream<int> streamMySessionsTodayCount() {
    final u = _auth.currentUser;
    if (u == null) return const Stream.empty();
    final now = DateTime.now();
    final startOfDay = DateTime(now.year, now.month, now.day);
    final ts = Timestamp.fromDate(startOfDay);
    return sessionsCol(u.uid)
        .where('createdAt', isGreaterThanOrEqualTo: ts)
        .snapshots()
        .map((qs) => qs.docs.length);
  }

  // ---------- Updates / Patches ----------
  static Future<void> updateUserProfile({
    String? country,
    String? gymName,
    String? experienceLevel,
    String? favoriteGroup,
  }) async {
    final u = _auth.currentUser;
    if (u == null) return;

    final patch = <String, dynamic>{};
    if (country != null) patch['country'] = country;
    if (gymName != null) patch['gymName'] = gymName;
    if (experienceLevel != null) patch['experienceLevel'] = experienceLevel;
    if (favoriteGroup != null) patch['favoriteGroup'] = favoriteGroup;

    if (patch.isEmpty) return;
    patch['updatedAt'] = FieldValue.serverTimestamp();
    await userDoc(u.uid).set(patch, SetOptions(merge: true));
  }

  static Future<void> setOnboardedTrue() async {
    final u = _auth.currentUser;
    if (u == null) return;
    await userDoc(u.uid).set({
      'onboarded': true,
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));
  }

  static Future<void> setSubscriptionPlan(String plan) async {
    final u = _auth.currentUser;
    if (u == null) return;
    await userDoc(u.uid).set({
      'subscription': {'plan': plan, 'updatedAt': FieldValue.serverTimestamp()},
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));
  }

  static Future<void> setCalibrationStatus({
    required bool completed,
    required String method, // 'photos' | 'skipped'
  }) async {
    final u = _auth.currentUser;
    if (u == null) return;
    final update = {
      'calibration': {
        'completed': completed,
        'method': method,
        'version': 1,
        if (completed) 'completedAt': FieldValue.serverTimestamp(),
      },
    };
    await userDoc(u.uid).set(update, SetOptions(merge: true));
  }

  /// Called by client **only when** analysis succeeded (frontend MVP).
  static Future<void> addSuccessfulSession({
    required String exerciseId,
    required int repsCount,
    required int goodReps,
    required int badReps,
    required String feedbackSummary,
    required String feedbackFull,
  }) async {
    final u = _auth.currentUser;
    if (u == null) return;
    await sessionsCol(u.uid).add({
      'exerciseId': exerciseId,
      'createdAt': FieldValue.serverTimestamp(),
      'repsCount': repsCount,
      'goodReps': goodReps,
      'badReps': badReps,
      'feedbackSummary': feedbackSummary,
      'feedbackFull': feedbackFull,
    });
  }

  // ---------- Subscription helpers ----------
  /// Derive entitlement purely from stored plan + endsAt (client-side display only).
  static String effectivePlanFrom(Map<String, dynamic> userData) {
    final sub = (userData['subscription'] as Map?) ?? {};
    final plan = (sub['plan'] ?? 'free').toString();
    final endsAt = sub['endsAt'];
    if (endsAt is Timestamp) {
      if (DateTime.now().isAfter(endsAt.toDate())) {
        return 'free';
      }
    }
    return plan;
  }

  /// UI-only "cancel" request: mark status so server can act later.
  static Future<void> requestCancelSubscription() async {
    final u = _auth.currentUser;
    if (u == null) return;
    await userDoc(u.uid).set({
      'subscription': {
        'status': 'cancel_requested',
        'cancelRequestedAt': FieldValue.serverTimestamp(),
      },
    }, SetOptions(merge: true));
  }
}
