import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:video_player/video_player.dart';
import 'package:http/http.dart' as http;

import '../config.dart';

class VideoUploadPage extends StatefulWidget {
  final String exerciseId; // e.g., "pushup"
  final String exerciseLabel; // e.g., "Push-ups"

  const VideoUploadPage({
    super.key,
    required this.exerciseId,
    required this.exerciseLabel,
  });

  @override
  State<VideoUploadPage> createState() => _VideoUploadPageState();
}

class _VideoUploadPageState extends State<VideoUploadPage> {
  final ImagePicker _picker = ImagePicker();
  File? _videoFile;
  VideoPlayerController? _videoController;

  bool _isBusy = false;

  // Parsed response bits
  String feedbackText = '';
  Map<String, dynamic>? metrics; // backend 'metrics' (per-rep + summary)
  Map<String, dynamic>? errorDetail; // backend error payload (when ok:false)

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _pickVideo() async {
    try {
      final picked = await _picker.pickVideo(
        source: ImageSource.gallery,
        maxDuration: const Duration(seconds: 30),
      );
      if (!mounted) return;
      if (picked == null) {
        _showSnack('No video selected');
        return;
      }
      _setVideo(File(picked.path));
    } catch (e) {
      _showSnack('Failed to pick video: $e');
    }
  }

  Future<void> _recordVideoWithCountdown() async {
    try {
      final cameraStatus = await Permission.camera.request();
      final micStatus = await Permission.microphone.request();
      if (!mounted) return;

      if (!cameraStatus.isGranted || !micStatus.isGranted) {
        _showSnack('Camera and microphone permissions are required');
        return;
      }

      await showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => const CountdownDialog(),
      );
      if (!mounted) return;

      final picked = await _picker.pickVideo(
        source: ImageSource.camera,
        maxDuration: const Duration(seconds: 30),
      );
      if (!mounted) return;
      if (picked == null) {
        _showSnack('Recording cancelled');
        return;
      }
      _setVideo(File(picked.path));
    } catch (e) {
      _showSnack('Failed to record video: $e');
    }
  }

  Future<void> _setVideo(File file) async {
    try {
      setState(() {
        _isBusy = true;
        // clear prior results
        feedbackText = '';
        metrics = null;
        errorDetail = null;
      });

      _videoFile = file;
      _videoController?.dispose();
      final controller = VideoPlayerController.file(file);
      _videoController = controller;
      await controller.initialize();
      if (!mounted) return;

      if (controller.value.duration > const Duration(seconds: 30)) {
        _showSnack('Video longer than 30s. Please trim and try again.');
        await controller.dispose();
        _videoController = null;
        setState(() => _isBusy = false);
        return;
      }

      controller.setLooping(false);
      setState(() => _isBusy = false);

      // Note: we no longer auto-upload here. User must tap "Submit".
    } catch (e) {
      _showSnack('Could not load video: $e');
      setState(() => _isBusy = false);
    }
  }

  Future<void> _uploadVideo(File file) async {
    setState(() {
      feedbackText = '';
      metrics = null;
      errorDetail = null;
      _isBusy = true;
    });

    try {
      final req =
          http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/analyze'))
            ..fields['exercise_id'] = widget
                .exerciseId // <-- pass the slug
            ..files.add(await http.MultipartFile.fromPath('video', file.path));

      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);

      if (!mounted) return;
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);

        if (data['ok'] == true) {
          setState(() {
            feedbackText = (data['agent_feedback'] ?? '').toString();
            metrics = (data['metrics'] as Map?)?.cast<String, dynamic>();
          });
        } else {
          // Show structured error with tips
          final tips =
              (data['tips'] as List?)?.map((e) => e.toString()).toList() ??
              const [];
          final reason = (data['reason'] ?? 'unknown').toString();
          setState(() {
            errorDetail = {'reason': reason, 'tips': tips};
            feedbackText = [
              "We couldn’t analyze that video.",
              if (reason.isNotEmpty) "Reason: $reason",
              if (tips.isNotEmpty) "",
              if (tips.isNotEmpty) "Tips:",
              if (tips.isNotEmpty) ...tips.map((t) => "• $t"),
            ].join('\n');
          });
        }
      } else {
        _showSnack('Backend error: ${res.statusCode}');
      }
    } catch (e) {
      _showSnack('Upload failed: $e');
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  Widget _buildStatsCard() {
    if (metrics == null) return const SizedBox.shrink();
    final summary =
        (metrics!['summary'] as Map?)?.cast<String, dynamic>() ?? {};
    final total = summary['total_reps'] ?? 0;
    final good = summary['good_reps'] ?? 0;
    final shallow = summary['shallow_reps'] ?? 0;
    final hipTwist = summary['hip_twist_reps'] ?? 0;
    final backNotNeutral = summary['back_not_neutral_reps'] ?? 0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFE0B2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFFCC80)),
      ),
      child: DefaultTextStyle(
        style: const TextStyle(fontSize: 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Summary — ${widget.exerciseLabel}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 16,
              runSpacing: 6,
              children: [
                Text('Total reps: $total'),
                Text('Good: $good'),
                Text('Shallow: $shallow'),
                Text('Hip twist: $hipTwist'),
                Text('Back not neutral: $backNotNeutral'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _videoController?.pause();
    _videoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Upload • ${widget.exerciseLabel}')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Preview (tap to play/pause)
              GestureDetector(
                onTap: () {
                  if (_videoController != null &&
                      _videoController!.value.isInitialized) {
                    final controller = _videoController!;
                    controller.value.isPlaying
                        ? controller.pause()
                        : controller.play();
                    setState(() {});
                  }
                },
                child: Container(
                  decoration: BoxDecoration(
                    color: Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFCC80)),
                  ),
                  padding: const EdgeInsets.all(12),
                  child:
                      _videoController != null &&
                          _videoController!.value.isInitialized
                      ? ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 240),
                          child: AspectRatio(
                            aspectRatio: 20 / 18, // your current chosen shape
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(8),
                                  child: VideoPlayer(_videoController!),
                                ),
                                if (!_videoController!.value.isPlaying)
                                  Container(
                                    decoration: const BoxDecoration(
                                      color: Color(0x40000000),
                                      shape: BoxShape.circle,
                                    ),
                                    padding: const EdgeInsets.all(12),
                                    child: const Icon(
                                      Icons.play_arrow,
                                      size: 40,
                                      color: Colors.white,
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        )
                      : const SizedBox(
                          height: 140,
                          child: Center(child: Text('No video selected')),
                        ),
                ),
              ),

              const SizedBox(height: 12),
              if (_isBusy) const LinearProgressIndicator(),
              const SizedBox(height: 12),

              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isBusy ? null : _recordVideoWithCountdown,
                      icon: const Icon(Icons.videocam),
                      label: const Text('Record (max 30s)'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isBusy ? null : _pickVideo,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload from Gallery'),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              if (_videoFile != null && !_isBusy)
                ElevatedButton.icon(
                  onPressed: () => _uploadVideo(_videoFile!),
                  icon: const Icon(Icons.send),
                  label: const Text('Submit for Upload'),
                ),

              const SizedBox(height: 16),

              // Stats (if any)
              if (metrics != null) _buildStatsCard(),
              if (metrics != null) const SizedBox(height: 12),

              // Feedback or error tips
              if (feedbackText.isNotEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFCC80),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFE0B2)),
                  ),
                  child: Text(
                    feedbackText,
                    style: const TextStyle(fontSize: 16, height: 1.35),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class CountdownDialog extends StatefulWidget {
  const CountdownDialog({super.key});

  @override
  State<CountdownDialog> createState() => _CountdownDialogState();
}

class _CountdownDialogState extends State<CountdownDialog> {
  int secondsLeft = 5;

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  void _startCountdown() {
    Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (secondsLeft == 1) {
        timer.cancel();
        Navigator.of(context).pop();
      } else {
        setState(() => secondsLeft--);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Get Ready'),
      content: Text('$secondsLeft…'),
    );
  }
}
