import 'package:flutter/material.dart';
import 'package:country_picker/country_picker.dart';
import '../services/db.dart';

class ProfileEditPage extends StatefulWidget {
  final String? initialCountry;
  final String? initialGymName;
  final String? initialLevel; // Beginner | Intermediate | Advanced
  final String? initialFavGroup; // Arms | Back | Chest | Legs | Shoulders | Abs

  const ProfileEditPage({
    super.key,
    this.initialCountry,
    this.initialGymName,
    this.initialLevel,
    this.initialFavGroup,
  });

  @override
  State<ProfileEditPage> createState() => _ProfileEditPageState();
}

class _ProfileEditPageState extends State<ProfileEditPage> {
  final _form = GlobalKey<FormState>();
  late String? _country = widget.initialCountry;
  late final _gymCtrl = TextEditingController(
    text: widget.initialGymName ?? '',
  );
  late String _experience = widget.initialLevel ?? 'Beginner';
  late String _fav = widget.initialFavGroup ?? 'Chest';
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
      onSelect: (c) => setState(() => _country = c.name),
    );
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    await Db.updateUserProfile(
      country: _country,
      gymName: _gymCtrl.text.trim().isEmpty ? null : _gymCtrl.text.trim(),
      experienceLevel: _experience,
      favoriteGroup: _fav,
    );
    if (!mounted) return;
    setState(() => _saving = false);
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final countryText = _country ?? 'Select country';

    return Scaffold(
      appBar: AppBar(title: const Text('Edit profile')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _form,
            child: ListView(
              children: [
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
                FilledButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.check),
                  label: const Text('Save'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
