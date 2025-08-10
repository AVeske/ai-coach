import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:video_player/video_player.dart';
import 'package:http/http.dart' as http;

import '../config.dart';

class VideoUploadPage extends StatefulWidget {
  final String exercise;
  const VideoUploadPage({super.key, required this.exercise});

  @override
  State<VideoUploadPage> createState() => _VideoUploadPageState();
}

class _VideoUploadPageState extends State<VideoUploadPage> {
  final ImagePicker _picker = ImagePicker();
  File? _videoFile;
  VideoPlayerController? _videoController;
  String aiFeedback = '';
  bool _isBusy = false;

  bool get _hasVideo =>
      _videoFile != null &&
      _videoController != null &&
      _videoController!.value.isInitialized;

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
      await _setVideo(File(picked.path));
    } catch (e) {
      _showSnack('Failed to pick video: $e');
    }
  }

  Future<void> _recordVideo() async {
    try {
      final cameraStatus = await Permission.camera.request();
      final micStatus = await Permission.microphone.request();
      if (!mounted) return;

      if (!cameraStatus.isGranted || !micStatus.isGranted) {
        _showSnack('Camera and microphone permissions are required');
        return;
      }

      final picked = await _picker.pickVideo(
        source: ImageSource.camera,
        maxDuration: const Duration(seconds: 30),
      );
      if (!mounted) return;
      if (picked == null) {
        _showSnack('Recording cancelled');
        return;
      }
      await _setVideo(File(picked.path));
    } catch (e) {
      _showSnack('Failed to record video: $e');
    }
  }

  Future<void> _setVideo(File file) async {
    try {
      setState(() {
        _isBusy = true;
        aiFeedback = '';
      });
      _videoFile = file;
      _videoController?.dispose();

      final controller = VideoPlayerController.file(file);
      _videoController = controller;
      await controller.initialize();
      if (!mounted) return;

      // Extra guard for max 30s
      if (controller.value.duration > const Duration(seconds: 30)) {
        _showSnack('Video longer than 30s. Please trim and try again.');
        await controller.dispose();
        _videoController = null;
        setState(() => _isBusy = false);
        return;
      }

      controller.setLooping(false);
      await controller.pause(); // start paused; tap to play
      setState(() => _isBusy = false);
    } catch (e) {
      _showSnack('Could not load video: $e');
      setState(() => _isBusy = false);
    }
  }

  Future<void> _uploadVideo(File file) async {
    setState(() {
      aiFeedback = '';
      _isBusy = true;
    });

    try {
      final req =
          http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/analyze'))
            ..fields['exercise'] = widget.exercise
            ..files.add(await http.MultipartFile.fromPath('video', file.path));

      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);

      if (!mounted) return;
      if (res.statusCode == 200) {
        setState(() => aiFeedback = res.body);
      } else {
        _showSnack('Backend error: ${res.statusCode}');
      }
    } catch (e) {
      _showSnack('Upload failed: $e');
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
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
      appBar: AppBar(title: Text('Upload • ${widget.exercise}')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Compact, portrait-style preview (tap to play/pause)
              GestureDetector(
                onTap: () {
                  if (_hasVideo) {
                    final v = _videoController!;
                    v.value.isPlaying ? v.pause() : v.play();
                    setState(() {});
                  }
                },
                child: Container(
                  decoration: BoxDecoration(
                    color: Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFCC80)),
                  ),
                  padding: const EdgeInsets.all(8),
                  child: Center(
                    child: _hasVideo
                        ? ConstrainedBox(
                            // ↓ make preview smaller/wider by changing maxWidth
                            constraints: const BoxConstraints(maxWidth: 240),
                            child: AspectRatio(
                              // ↓ change this to adjust shape (e.g., 3/4, 9/16, 2/3)
                              aspectRatio: 14 / 15,
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
                                        color: Color(0x40000000), // ~25% black
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
              ),

              const SizedBox(height: 12),
              if (_isBusy) const LinearProgressIndicator(),
              const SizedBox(height: 12),

              // Pick/Record row
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isBusy ? null : _recordVideo,
                      icon: const Icon(Icons.videocam),
                      label: const Text('Record'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isBusy ? null : _pickVideo,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload'),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              // Submit only after a video is ready and not busy and no feedback yet
              if (_hasVideo && !_isBusy && aiFeedback.isEmpty)
                ElevatedButton.icon(
                  onPressed: () => _uploadVideo(_videoFile!),
                  icon: const Icon(Icons.send),
                  label: const Text('Submit for Feedback'),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size.fromHeight(48),
                  ),
                ),

              const SizedBox(height: 16),

              // Feedback panel
              if (aiFeedback.isNotEmpty)
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFCC80),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFFFE0B2)),
                    ),
                    child: SingleChildScrollView(
                      child: Text(
                        aiFeedback,
                        style: const TextStyle(fontSize: 16, height: 1.35),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
