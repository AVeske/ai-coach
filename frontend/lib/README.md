# Frontend Documentation

# **Main.dart**

### Imports

- `flutter/material.dart` - Provides widgets such as `MaterialApp`, `StatelessWidget`, `BuildContext`, `ThemeMode`.

- `theme.dart` - Local file in the project that defines the app's LIGTH and Dark modes ( `AppTheme.light` and `AppThere.dark`).

- `pages/home_page.dart` - Local file that defines the `HomePage` widget, which is set as the first screen when the app runs

### `main()` Function

- `void main()` - This is the **entry point** of every Flutter app.

- Calls `runApp()` with the root widget `AICoachApp` to start rendering the UI.

### `AICoachApp` Class

- **Type**: `StatelessWidget` (from Flutter's `material.dart`)

- **Purpose**: Represents the \*_root widget_' of the application.

- **Constructor**:
  - Uses `const` constructor for performance (no rebuilding when nothing changes).
  - Accepts an optional `key` parameter (inherited from `StatelessWidget`) for widget tree indentification

### `build()` Method

- **Returns**: `MaterialApp` widget, the root-level Material Design wrapper for the app.
- **Parameters passed to `MaterialApp`**:
  - `title`: Sets the app's title (Used by the OS in places like task switchers).
  - `debugShowCheckedModeBanner: false`: Removes the "DEBUG" banner in debug mode.
  - `theme: AppTheme.light`: Loads the **light theme** defined in `theme.dart`
  - `darkTheme: AppTheme.dark`: Loads the **dark theme** defined in `theme.dart`
  - `themeMode: ThemeMode.system`: Adapts to the device's system theme (light/dark).
  - `home: const HomePage()`: Sets the **HomePage widget** (defined in `pages/home_page.dart`) as the starting screen

## Data Flow / Widget Connections

- `main()` -> starts the app with `runApp()`
- `AICoachApp` -> builds -> `MaterialApp`
- `MaterialApp` -> sets `home` -> `HomePage` and applies **themes** from `AppTheme`
- `HomePage` (from `home_page.dart`) is where the user lands when opening the app.
- `AppTheme.light` and `AppTheme.dark` are pulled in from `theme.dart` to provide styling.

## Widgets / Concept Glossary

- `StatelessWidget`: Base class for widgets without internal mutable state. Good for "static" UI (like headers, navigation shells).
- `BuildContext`: Object that holds information about where a widget is in the widget tree (used when building UIs or finding parents)
- `MaterialApp`: Root-level widget that sets up Material Design defualts (themes, navigation, text direction).
- `ThemeMode`: Enum that tells Flutter whether to use `light`, `dark`, `system` theme mode.
- `HomePage`: The app's first screen (defined seperately in `home_page.dart`).

# **Theme.dart**

This file defines the **visual style (theme)** of the entire Flutter app.
Flutter allows apps to have **light** and **dark** themes, and this file configures both under the `AppTheme` Class.

### Imports

- `flutter/material.dart`: Flutter's Material Designe package, providing read-made UI widgets (`AppBarTheme`, `ThemeData`, `ElevatedButtonThemeData`, etc.).

### `AppTheme` Class

- **Type**: Simple Dart Class (not a widget).
- **Purpose**: Encapsulates theme definitions (light & dark) so they can be imported and reused in `main.dart`

#### `light` Theme

- Defines the **default colors, typography, and shapes** for the **light mode**.
- `colorScheme`: Generate a palette based on a seed color (`#EA580C`, a deep orange).
- `useMaterial3`: Enables **Material You** (latest Material Designe 3 spec).
- `scafoldBackgroundColor`: Sets background for all screens (`#F8FAFC`, light gray)
- `appBarTheme`: Styles the top app bar -> centered title, flat(0 elevation), white background, black text.
- `elevatedButtonTheme`: Styles all `ElevatedButton` widgets -> padding, font, rounded corners.
- `inputDecorationTheme`: Styles from fields -> rounded borders

#### `dark` Theme

- Starts from Flutter's **default dark theme** (`ThemeData.dark`)
- Customizes:
  - `colorScheme`: Uses orange (`#FB923C`) as primary and secondary brand color.
  - `elevatedButtonTheme`: Same rounded, padding styles as light theme.
  - `appBarTheme`: Keeps centered titles.

## Data Flow / Usage

- `AppTheme.light` and `AppTheme.dark` are **imported in `main.dart`** and applied to the `MaterialApp`.
- Depending on system setting (`ThemeMode.system`), Flutter automatically switches between **light** and **dark** versions.

## Widget/Concept Glossary

- `ThemeData`: Central object in Flutter that defines colors, text styles, and shapes for the entire app.
- `ColorScheme`: Standard Material Design set of colors (`primary`, `secondary`, `error`, `surface` etc.)
- `AppBarTheme`: Configures styling for all `AppBar`s (navigation bar at the top).
- `ElevatedButtonThemeData`: Defines default look for raised buttons.
- `InputDecorationTheme`: Defines how text fields look (borders, padding, labels).
- **Material 3** (`useMaterial3`): Latest design spec from Google, focusing on dynamic color, adaptive shapes, and smoother UI.

# **Config.dart**

This file centralizes the **backend API base URL** used by Flutter app to call your FastAPI server.

### What this controls

Every network call in the app (e.g., uploading videos tp `/analyze` (recieving API name)) builds URLs off `apiBaseURL`. Chaning this constant points the app to a different backend.

### Which URl should I use?

- **Physical Device on same Wi-Fi**
  - Use your PC's LAN IP (found via `ipconfig`/`ifconfig`)
  - **Make sure phone & PC are on the same network, and the PC firewall allows inbound on 8000**
- **iOS Simulator (on macOS)**
  - Use: `http://localhost:8000`(or `http://127.0.0.1:8000`) -**Hosted/Staging/Production**
  - Use your public URL, ideally **HTTPS**, e.g. `https://api.domainname.com`
  - Configure CORS in FastAPI and SSL (via your cloud/load balancer/reverse proxy)

## Glossary

- Base URL: The server root the app talks to; endpoints are appended (e.g., /analyze).

- 10.0.2.2: Android emulator’s alias to the host machine’s localhost.

- CORS: Cross-Origin Resource Sharing; server setting that permits your app’s origin to call it.

- ATS (iOS): App Transport Security; enforces HTTPS unless you add exceptions.

- Dart define: Build-time constants you inject with --dart-define, read via String.fromEnvironment.
