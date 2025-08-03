import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:video_player/video_player.dart';

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

  Future<void> _pickVideo() async {
    final status = await Permission.photos.request();
    if (!mounted) return;

    if (!status.isGranted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Gallery access denied')));
      return;
    }

    final picked = await _picker.pickVideo(
      source: ImageSource.gallery,
      maxDuration: const Duration(seconds: 30),
    );
    if (!mounted) return;

    if (picked != null) {
      _setVideo(File(picked.path));
    }
  }

  Future<void> _recordVideoWithCountdown() async {
    final cameraStatus = await Permission.camera.request();
    final micStatus = await Permission.microphone.request();
    if (!mounted) return;

    if (!cameraStatus.isGranted || !micStatus.isGranted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Camera and microphone permissions are required"),
        ),
      );
      return;
    }

    await showDialog(
      context: context,
      builder: (ctx) => const CountdownDialog(),
    );
    if (!mounted) return;

    final picked = await _picker.pickVideo(
      source: ImageSource.camera,
      maxDuration: const Duration(seconds: 30),
    );
    if (!mounted) return;

    if (picked != null) {
      _setVideo(File(picked.path));
    }
  }

  void _setVideo(File file) {
    _videoFile = file;
    _videoController?.dispose();
    _videoController = VideoPlayerController.file(file)
      ..initialize().then((_) {
        if (!mounted) return;
        setState(() {});
        _videoController?.setLooping(true);
        _videoController?.play();
        _getAiFeedback();
      });
  }

  void _getAiFeedback() async {
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    setState(() {
      aiFeedback = "Not bad, bro. Just squeeze your chest more at the top.";
    });
  }

  @override
  void dispose() {
    _videoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Upload for ${widget.exercise}')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            if (_videoController != null &&
                _videoController!.value.isInitialized)
              AspectRatio(
                aspectRatio: _videoController!.value.aspectRatio,
                child: SizedBox(
                  height: 180,
                  child: VideoPlayer(_videoController!),
                ),
              )
            else
              Container(
                height: 180,
                color: Colors.black12,
                alignment: Alignment.center,
                child: const Text("No video selected"),
              ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: _recordVideoWithCountdown,
              icon: const Icon(Icons.videocam),
              label: const Text("Record Video (max 30s)"),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
              ),
            ),
            const SizedBox(height: 10),
            ElevatedButton.icon(
              onPressed: _pickVideo,
              icon: const Icon(Icons.upload_file),
              label: const Text("Upload from Gallery"),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
              ),
            ),
            const SizedBox(height: 30),
            if (aiFeedback.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.orange.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.fitness_center, size: 28),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        aiFeedback,
                        style: const TextStyle(fontSize: 16),
                      ),
                    ),
                  ],
                ),
              ),
          ],
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
        setState(() {
          secondsLeft--;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Get Ready!'),
      content: Text('$secondsLeft...'),
    );
  }
}
