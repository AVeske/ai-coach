# **exercise.dart**

Defines the **core exercise model** and related utilities:

- Groups exercises into categories (`chest`, `back`, `arms`, `legs`).
- Stores metadata for each exercise (id, group, name).
- Provides lookup helpers (`byGroup`, `groupLabel`).
- Supplies a **seed dataset** for the UI to display.

### `enum ExerciseGroup`

- Defines **categories of exercises.**
- Used to group exercises in the UI.
- Prevents typos compared to string labels (`ExerciseGroup.chest` vs `chset`)

### `Exercise` Class

- **Fields**
  - `id`: unique identifier (used interally, API calls, YAML configs).
  - `group`: `ExerciseGroup` enum (muscle group).
  - `name`: User-friendly label displayed in UI.
- **const constructor**: Makes objects immutable and useable in compile-time constants.
- Instances are created as constants in the seed data.

### const `exercises`

- A static dataset of exercises.
- Each item links to a muscle group.
- The app uses this for:
  - Building exercse lists.
  - Mapping UI selections to IDs used in backend scoring
- `Exercise(id: 'pushup', group: ExerciseGroup.chest, name: 'Push-ups')` : Internally identified as "pushup", but user sees "Push-ups".

### `List<Exercise> byGroup(ExerciseGroup group)`

- Utility function
- Returns al lexercises in a given group.
- Used in `exercise_list_page.dart` to build filtered lists.

### `String groupLabel(ExerciseGroup g)`

- Converts enum values into **human-friendly strings**
- Used in UI titles and navigation bars.

## Data Flow / Connections

- `Exercise` object -> defined here
- `byGroup` and `groupLabel` -> called by `exercise_list_page.dart`
- `exercise_list_page.dart` builds `ExerciseTile` widgets using these objects.
- When tapped, each `Exercise` is passed to `video_upload_page.dart` for recording/upload.

## Glossary

- `enum` -> A special type that defines a fixed set of constant values.
- `const` constructor -> Ensures objects are immutable and reusable at compile-time.
- **Immutability** -> Once created, exercise objects cannot be changed, ensuring safety in lists and UI.
