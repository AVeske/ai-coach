import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/material.dart';

class AppPrefs {
  static const _kTheme = 'themeMode';
  static const _kCalibrationDone = 'calibrationCompleted';

  static Future<bool> calibrationDone() async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kCalibrationDone) ?? false;
    // false means: show calibration flow
  }

  static Future<void> setCalibrationDone([bool v = true]) async {
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kCalibrationDone, v);
  }

  static Future<ThemeMode> loadTheme() async {
    final p = await SharedPreferences.getInstance();
    final s = p.getString(_kTheme);
    switch (s) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      case 'system':
      default:
        return ThemeMode.system;
    }
  }

  static Future<void> saveTheme(ThemeMode mode) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kTheme, mode.name);
  }
}
