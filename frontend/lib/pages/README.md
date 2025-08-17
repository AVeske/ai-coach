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

# **home_page.dart**
