# **exercise_tile.dart**

`ExerciseTile` is a **reusable UI component** that displays a single exercise in a list.

- It shows the exercise name (`title`) and a forward arrow icon.
- It responds to user taps and triggers a callback (`onTap`).
- It uses theming to adapt colors dynamically (light/dark mode).

### Imports

- `flutter/material.dart`
  - Provides **Flutter Material Design widets** such as:
    - `StatelessWidget`
    - `InkWell`, `Ink`, `Text`, `Row`, `Icon`
    - `Theme`, `BorderRadius`, `BoxDecoration`
    - `VoidCallback`

### `ExerciseTile` Class

- `StatelessWidget`: Immutable widget, rebuilt entirely when parent state changes.
- **Fields**:
  - `title`: label to display (exercise name).
  - `onTap`: Function exercuted when tile is tapped (navigation, etc.)
  - `onInfo`: Adds a info button on how to correctly film for best result.(from `exercise.dart`)

### `build()` Method

- **Key Widgets**
  - `Theme.of(context).colorScheme.primary`: Dynamically pulls the app's primary color (orange in light mode, orange in dark mode as defined in `theme.dark`).
  - `InkWell`: Detects taps and provides ripple effect inside rounded borders.
  - `Ink`: Provides background decoration for the ripple
  - `BoxDecoration`: Rounded corners + border (primary color at 15% opacity) + background color.
  - `Row`: Aligns title text left, arrow icon right.
  - `Expanded`: Forces text to take available space, pushing arrow icon to the far right.

## Data Flow / Widget Connections

- **Input**: `title` (string), `onTap` (function).
- **Output**: UI tile rendered inside lists.
- **Interaction**: When tapped, `onTap` is executed -> navigates to `VideoUploadPage`.
- **Used in**: `exercise_list_page.dart` -> builds a list of these tiles using exercise data from `exercise.dart`.

## Glossary

- `StatelessWidget`: A widget with no internal state. All changes come from parent widgets.
- `VoidCallback`: Typedef for a function with no arguments and no return value, commonly used for event handlers.
- `Inkwell`: Material widget providing ripple animations for tap gestures.
- `Theme.of(context)`: Accesses app-wide them data (`AppTheme.light` / `AppTheme.dark`).
- `Expanded`: Expands child widget to fill available space within a `Row` or `Column`
