import 'package:flutter/material.dart';
import 'package:country_picker/country_picker.dart';
import '../services/db.dart';

class ProfileSetupPage extends StatefulWidget {
  final VoidCallback onDone;
  const ProfileSetupPage({super.key, required this.onDone});

  @override
  State<ProfileSetupPage> createState() => _ProfileSetupPageState();
}

class _ProfileSetupPageState extends State<ProfileSetupPage> {
  final _form = GlobalKey<FormState>();
  String? _country;
  final _gymCtrl = TextEditingController();
  String _experience = 'Beginner';
  String _fav = 'Chest';
  bool _saving = false;

  static const _groups = ['Arms', 'Back', 'Chest', 'Legs', 'Shoulders', 'Abs'];
  static const _levels = ['Beginner', 'Intermediate', 'Advanced'];

  @override
  void dispose() {
    _gymCtrl.dispose();
    super.dispose();
  }

  void _pickCountry() {
    showCountryPicker(
      context: context,
      showPhoneCode: false,
      showWorldWide: false,
      useSafeArea: true,
      countryListTheme: CountryListThemeData(
        inputDecoration: const InputDecoration(
          labelText: 'Search country',
          prefixIcon: Icon(Icons.search),
        ),
      ),
      onSelect: (Country c) => setState(() => _country = c.name),
    );
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    await Db.updateUserProfile(
      country: _country,
      gymName: _gymCtrl.text.trim(),
      experienceLevel: _experience,
      favoriteGroup: _fav,
    );
    await Db.setOnboardedTrue();
    if (!mounted) return;
    setState(() => _saving = false);
    widget.onDone();
    Navigator.pop(context); // back to router -> Home
  }

  Future<void> _skip() async {
    setState(() => _saving = true);
    await Db.setOnboardedTrue();
    // mark calibration “skipped” so it won’t prompt again later
    await Db.setCalibrationStatus(completed: true, method: 'skipped');
    if (!mounted) return;
    setState(() => _saving = false);
    widget.onDone();
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final countryText = _country ?? 'Select country';
    return Scaffold(
      appBar: AppBar(title: const Text('Set up your profile')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _form,
            child: ListView(
              children: [
                const Text(
                  'These help us personalize your feedback. You can change them anytime.',
                  style: TextStyle(height: 1.3),
                ),
                const SizedBox(height: 16),

                // Country picker (searchable)
                TextFormField(
                  readOnly: true,
                  controller: TextEditingController(text: countryText),
                  decoration: InputDecoration(
                    labelText: 'Country',
                    suffixIcon: _country == null
                        ? const Icon(Icons.public)
                        : IconButton(
                            tooltip: 'Clear',
                            icon: const Icon(Icons.close),
                            onPressed: () => setState(() => _country = null),
                          ),
                  ),
                  onTap: _pickCountry,
                  validator: (v) => (_country == null || _country!.isEmpty)
                      ? 'Pick a country'
                      : null,
                ),

                const SizedBox(height: 12),
                TextFormField(
                  controller: _gymCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Gym name (optional)',
                  ),
                ),
                const SizedBox(height: 12),

                DropdownButtonFormField<String>(
                  value: _experience,
                  decoration: const InputDecoration(
                    labelText: 'Experience level',
                  ),
                  items: _levels
                      .map((l) => DropdownMenuItem(value: l, child: Text(l)))
                      .toList(),
                  onChanged: (v) =>
                      setState(() => _experience = v ?? _experience),
                ),
                const SizedBox(height: 12),

                DropdownButtonFormField<String>(
                  value: _fav,
                  decoration: const InputDecoration(
                    labelText: 'Favorite group',
                  ),
                  items: _groups
                      .map((g) => DropdownMenuItem(value: g, child: Text(g)))
                      .toList(),
                  onChanged: (v) => setState(() => _fav = v ?? _fav),
                ),

                const SizedBox(height: 20),
                if (_saving) const LinearProgressIndicator(),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.check),
                  label: const Text('Save & continue'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: _saving ? null : _skip,
                  child: const Text('Skip for now'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
