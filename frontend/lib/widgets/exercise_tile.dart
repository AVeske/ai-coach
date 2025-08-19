import 'package:flutter/material.dart';

class ExerciseTile extends StatelessWidget {
  final String title;
  final VoidCallback onTap;
  final VoidCallback? onInfo; // NEW
  final String infoTooltip; // NEW

  const ExerciseTile({
    super.key,
    required this.title,
    required this.onTap,
    this.onInfo,
    this.infoTooltip = 'Filming tip',
  });

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Ink(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.15)),
          color: Theme.of(context).cardColor,
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (onInfo != null)
                IconButton(
                  tooltip: infoTooltip,
                  icon: const Icon(Icons.info_outline),
                  onPressed: onInfo,
                ),
              Icon(
                Icons.arrow_forward_ios,
                size: 16,
                color: color.withOpacity(0.7),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
