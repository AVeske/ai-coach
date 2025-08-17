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
  final String exercise; // slug e.g. "pushup"
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
      _setVideo(File(picked.path));
    } catch (e) {
      _showSnack('Failed to record video: $e');
    }
  }

  Future<void> _setVideo(File file) async {
    try {
      setState(() => _isBusy = true);
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

      controller.setLooping(false); // tap to play/pause
      setState(() => _isBusy = false);
      // No auto-upload — user must press Submit.
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
            ..fields['exercise_id'] = widget.exercise
            ..files.add(await http.MultipartFile.fromPath('video', file.path));

      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);

      if (!mounted) return;
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() => aiFeedback = data['agent_feedback'] ?? 'Success');
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
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              GestureDetector(
                onTap: () {
                  if (_videoController != null &&
                      _videoController!.value.isInitialized) {
                    final c = _videoController!;
                    c.value.isPlaying ? c.pause() : c.play();
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
                            aspectRatio: 14 / 15,
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: VideoPlayer(_videoController!),
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
                      onPressed: _isBusy ? null : _recordVideo,
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

              if (aiFeedback.isNotEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFCC80),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFFE0B2)),
                  ),
                  child: Text(
                    aiFeedback,
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
