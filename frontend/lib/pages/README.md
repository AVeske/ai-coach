# **exercise_list_page.dart**

Screen that shows all exercises for a selected **muscle group**, provides a **search box**, and navigates to the **video upload page** for those exercise.

### Imports

- `material.dart`: Flutter UI widgets ( Scaffold, AppBar, TextField, ListView, etc.).
- `models/exercise.dart`: Exercise data (`Exercise`, `ExerciseGroup`, `byGroup`, `groupLabel`).
- `widgets/exercise_tile.dart`: Reusuable row UI for an exercise item.
- `video_upload_page.dart`: Target page after a user picks an exercise.

### `ExerciseListPage` Class (StatefulWidget)

- **Purpose**: Screen that lists exercises for a chose muscle group and lets the user pick one.
- **Input**: `group: ExerciseGroup` (Provided by the caller, e.g. from `HomePage`).
- **Output/Side-effects**: When a list item is tapped, pushes `VideoUploadPage` (navigation)
- **Created state via**: `createState()` -> return `_ExerciseListPageState`.

### `_ExerciseListPageState` Class:

-**Purpose**: Holds mutable UI state (search query) and builds the list UI.

- **Fields**: `_query: String`
  - **What it is**: The current search text.
  - **How it's set**: In `TextField.onChange` via `setState`.
  - **What it affects**: Filters which exercises are visible.

### `_openExercise(Exercise ex)` Method

- **Purpose**: Handle taps on a list row.
- **Input**: The tapped `Exercise` (from the visible list).
- **Action**: `Navigator.push(...)` to `VideoUploadPage(exercise: ex.id)`
- **Contract**: uses `ex.id` to identify the exercise for the backend.

### `build(BuildContext)` Method

- **Purpose**: Compose the UI based on current state and widget input.
- **Reads**:
  - `widget.group` -> which group to list.
  - `_query` -> filter text
- **Steps**:
  1. `final all = byGroup(widget.group)` - get all exercises for the group.
  2. `final visible = all.where(..._query...).toList();` - filter by name.
  3. Build UI:
     - `Scaffold`: Page shell
     - `Appbar(title: groupLabel(widget.group))`: Shows group name
     - `SafeArea`: Avoids notches
     - `Padding(16)`: consistent margins.
     - `Column`:
       - `TextField`(search): updates `_query` vis `setState` -> triggers rebuild.
       - `SizedBox(height: 12)`: Spacing
       - `Expanded(ListView.separated)`:

## Data Flow

- Source of truth for exercises: `model/exercise.dart` -> `exercises` + `byGroup(group)` + `groupLabel(group)`.
- Filtering occurs **client-side** using `_query` only; ther is no backend query here.
- Navigation passes the **exercise id** (not the label) to the upload page, which uses it when calling the backend.

## Glossary

- `StatefulWidget` / `State<T>`: Two-part widget pattern. `StatefulWidget` is the immutable configuration; the mutable UI/state lives in `State<T>`. `build()` is defined on the State class.

- `extends`: Inheritance in Dart. `_ExerciseListPageState` extends `State<ExerciseListPage>`, meaning it implements the behavior and lifecycle for that widget.

- Leading underscore (`_`): Marks a library-private class/field/function in Dart (not accessible from other files).

- `Navigator.push` + `MaterialPageRoute`: Standard Flutter navigation; pushes a new page onto the stack.

- `setState()`: Notifies Flutter that state changed; triggers a rebuild.

- `Expanded`: Forces its child to take the remaining space in a `Column` or `Row`.

- `SafeArea`: Adds padding to avoid notches, status bar, and system UI intrusions.

# **exercise_group_page.dart**

This file defines the **Home Page** of the AI Coach app. It acts as the entry point after launch, where the user selects which body part (exercise group) they want to train.
It consists of two main widgets:

- `HomePage`: The page with an AppBar and a grid of exercise groups.
- `_GroupCard`: A reusable widget representing a selectable card for each exercise group.
  In simple terms: This page acts as the routing hub into exercise selection, with no backend calls yet — all data is local (from exercise.dart).

### `HomePage` Class

**Purpose**:

- Displays a grid of body-part groups (chest, back, arms, legs).
- Handles navigation into the `ExerciseListPage` for the chosen group.

  **Key Components**:

- **Constructor**: `const HomePage({super.key});`. No external inputs besides Flutter's key.
- **Method** `_openGroup(BuildContext, Exercise group)`:
  - Input: `context` (navigation context), `group` (enum value).
  - Action: Uses `Navigator.push` to transition to `ExerciseListPage`, passing the selected `ExerciseGroup` as an argument.
  - Output: A new page is pushed onto the navigation stack.
- **Method** `build(BuildContext context)`:
  - Retrieves all available groups via `ExerciseGroup.values`.
  - Builds the UI: `Scaffold`, `Column`, `GridView.builder`(that iterates over all exercise groups and creates `_GroupCard` widgets
  - Data Flow:
    - Calls `groupLabel(g)` (from `model/exercise.dart`) to get the human-readable name of each enum value.
    - Passes `onTap: () => _openGroup(context, g)` to `GroupCard` so the correct navigation heppens when tapped.

### `_GroupCard` Class

**Purpose**:

- Displays a clickable card with a gradient background and the title of the group.
- Calls a callback when tapped.
  **Key Components**:
- **Constructor**: `const _GroupCard({required this.title, required this.onTap});`
  - Input:
    - `title`: String -> Label of the group (from `groupLabel()`)
    - `onTap`: VoidCallback -> Triggers navigation when tapped
- **Method** `build(BuildContext context)`
  - UI:
    - `Inkwell`: Provides tap interaction and ripple effect.
    - `Ink`: Holds decoration(rounded rectangle, gradient, border).
    - `Center -> Text`: Displays the group title with styling.
  - Data Flow:
    - When tapped -> `onTap` Exercutes -> Calls `_openGroup` in HomePage
    - This pushes `ExerciseListPage` onto the stack with the selected `ExerciseGroup`

## Data Flow / Widget Connections

1. `HomePage.build`
   - Loads all exercise groups (`ExerciseGroup.values`).
   - Creates `_GroupCard` for each group.
2. User taps `_GroupCard`
   - `_GroupCard.onTap` triggers `_openGroup(context, group)`.
3. Navigation
   - `_openGroup` uses `Navigator.push` -> builds `ExerciseListPage(group: g)`
   - Data passes: `ExerciseGroup` enum value.
4. Downstream
   - `ExerciseListPage` then shows a list of exercises filtered by that group

## Glossary

- `StatelessWidget`: A widget with no internal state; its output depends solely on its input. Both `HomePage` and `_GroupCard` are stateless
- `Navigator.push`: Flutter's navigation API; pushes a new screen (page) onto the stack.
- `MaterialPageRoute`: A Route that transitions to a new screen with Material design animations.
- `GridView.builder`: Efficiently builds grid items on demand.
- `ExerciseGroup`: Enums defined in `exercise.dart` (chest, back, arms, legs)
- `groupLabel()`: Function mapping enum -> user-friendly string ("Chest", "Back", etc.)
- **Leading underscore (\_) in** `_GroupCard`: Marks the class as **private to thsi file**. It cannot be imported or used outside `home_page.dart`

# **video_upload_page.dart**

Screen where the user records or selects a short video (≤30s) for the chosen exercise, previews it, then manually submits it to the backend /analyze. Shows the AI feedback text returned by the API.

### Imports

- `dart:async`, `dart:convert`, `dart:io` - async ops, JSON decoded, fail handle
- `package:flutter/material.dart` - UI, `Scaffold`, `SnackBar`, etc.
- `image_picker` - opens camera or gallery to capture/pick a video file.
- `permission_handler` - requests camera and microphone runtime permissions (Android/iOS)
- `video_player` - lightweight video preview player (tap to play/pause)
- `http` - upload the selected file as multipart to FastAPI.
- `../config.dart` - read `apiBaseUrl`

### `VideoUploadPage` Class

**Purpose**: Ties a specific exercise (slug like `pushup`) to a video upload flow.
**Public API**

- `VideoUploadPage({required String exercise})`: `exercise` is sent as `exercise_id` to the backend.
  **Created State**: `_VideoUploadPageState`.

### `_VideoUploadPageState` Class

**Fields**

- `_picker (ImagePicker)` - media source.
- `_videoFile (File?)` - currently selected/recorded local file.
- `_videoController (VideoPlayerController?)` - preview controller
- `aiFeedback(String)` - text returned by backend.
- `_isBusy(bool)` - disable UI when work in progress

**Helper**

- `_showSnack(String)` - safe snack message if `mounted`
  **Key Method**
- `_pickVideo()`: Opens Gallery, cps duration to 30sec. On success -> `_setVideo(file)`. Handles cancel & exceptions.
- `_recordVideo()`
  1. Requests `camera` + `microphone` via `permission_handler`.
  2. Opens camera recorder, caps 30sec.
  3. On success -> `_setVideo(file)`
- `_setVideo(File)`: Initializes `VideoPlayerController.file`, rejects clips over 30sec, sets no auto-loop (user taps to play/pause). Does NOT auto-upload; user must press **Submit**
- `_uploadVideo(file)`: Builds `MultipartRequest` to `POST $apiBaseUrl/analyze` with:
  - field: `exercise_id = widget.exercise`
  - file: `video=@path`
  - Awaits response -> `aiFeedback = data["agent_feedback"]` or shows error. Wraps calls with `_isBusy` and error snackbars.
  - `dispose()`: Pauses & disposes the `VidePlayerController`

### `build()` Method (UI structure)

- `Scaffold` -> `BarApp("Upload * <exercise>")`
- `SingleChildScrollView` with padding:
  - Preview Card:
    - If video read -> constrained box (phone-ish aspect), tap to play/pause.
    - Else placeholder "No vide selected".
  - Busy bar (`LinearProgressIndicator`) when `_isBusy`
  - Row of actions:
    - "Record (max 30sec)" -> `_recordVideo()`
    - "Upload from Gallery" -> `_pickVideo()`
  - **Submit** button (only visible when `_videoFile != null` & not busy) -> `_uploadVideo(_videoFile!)`
  - **Feedback panel** (when `aiFeedback.isNotempty`) - scrolls with page

## Data Flow

1. Page created with `exercise` slug (from `ExerciseListPage`)
2. User **records** or **picks** video -> `_setVideo()` initializes preview.
3. User presses **Submit** -> `_uploadVideo()` -> FastAPI `/analyze`
4. Backend return JSON -> `aiFeedback` rendered in the feedback panel

## Notes /Gotchas

- **30s limit** enforced client-side; backend should still validate.
- **Tap-to-play preview** uses `video_player`; large videos aren't stored - only local temp file.

## Glossary

- `StatefulWidget`: widget with mutable state across frames.
- `mounted`: flag that the State is still in widget tree; check before UI ops.
- `ImagePicker.pickVideo`: opens camera/gallery; returns XFile?.
- `VideoPlayerController.file`: controller to render local video in a widget.
- `MultipartRequest`: HTTP form upload; used to send file + fields.
- `SnackBar`: transient message at bottom of screen for errors/status.
