# **Chest**

# **Back**

# **Arms**

# **Legs**

## **Chest_scorers.py**

### **Helper Functions**

### - **\_shape_score(valley, bottom_idx) -> float**

**Purpose**: Rate wjetjer tje elbow-angle valley (top-bottom-top) looks like a clean single dip
**Steps**:

1. Copy to float, guard tiny windows /all-NaN -> return 0.0 early.
2. Normalize the segment to [0..1] using finite min/max.
3. Apply `median_smooth(arr, 3)` to remove tiny jaggies.
4. Take first difference `d = np.diff(arr)`.
   - Left side (up to bottom): should be mostly decreasing ( d <= 0)
   - Right side (after bottom): should be mostly increasing (d >= 0).
5. Count directional violations on each side (`left_viol`, `right_viol`)
6. Compute a symmetry factor = min (left_len,right_len)/max(...).
7. Combine: `score = 0.5*(left_ok + right_ok) * (0.5 + 0.5*symmetry)` in [0..1].
   **Use**: a soft quality gate to flag "shape_poor" if the motion doesn't look like one clean dip.

### - **\_merge_refactory(reps, fps, refactory_ms) -> reps**

**Purpose**: prevent double-counting reps that are too close together.

- Convert `refactory_ms` into a frame gap.
- If the next rep's start is within that gap from previous rep's end, merge:
  - Keep the earliest start, the later end, and pick a reasonable bottom.
- Otherwise, append as a separate rep.
  **Use**: after initiaö span pairing, to collapse "stutter" deteactions into one rep.

### - **\_dynamic_thresholds(y_series, bottom_pct, top_pct) -> disct**

**Purpose**: compute global shoulder-Y bands from precentiles.

- Mask NaN's
- `bottom = P(bottom_pct)` e.g. 72nd precentile (typical bottom).
- `top = P(top_pct)` e.g. 28th precentile (typical top).
- `mid = (bottom+top)/2`.
  **Use**: later per-rep to check if the bottom frame actually reached a typical bottom zone.

### - **\_local_bottom_ok(sh, t1, bot, t2, margin=0.06) -> bool**

**Purpose**: fallback confirmation if global bands fail.

- Slice shoulder'Y over this rep's window `[t1:t2]`.
- Get the local max (largest Y -> lowest shoulder position).
- Require `sh[bot] >= local_max - margin`.
  This says: "your bottom frame is near the best bottom within this rep."
  **Use**: avoids missing reps just beacause the global precentile band was off.

### - **\_span_dur_ok(t1, t2, fps, dur_min, dur_max, slack=1.25)**

- Compute duration in seconds
- Accept if in `[dur_min, dur_max*slack]`
  **Use** guard against absurdly long spans (e.g., elbows events mis-paired over many seconds).

### - **\_filter_spans(span, fps, dur_min, dur_max, slack=1.25)**

- Split a list of spans into `kept` vs `dropped` using `_spam_dur_ok`
  **Use**: applied to elbow_based spans and shoulder-based spans before choosing the segmentation.

## **Main Scorers**

### **score_pushup(sample, fps, cfg, primary_side="left") -> dict**

**Purpose**: detect reps and grade them. Emit every plausible rep (do not drop for flags), and attack flags/grades. Return per-rep detail + summary + debug.

**Input**

- `sample`: trimmed + smoothed pose samples (list of discts with `"landmarks"` per frame).
- `fps`: sampled fps (~15).
- `cfg`: YAML config dict for pushups (events, metrics, bad flags).
- `primary_side`: global side already chosen upstream.

**Configuration extraction**

- Pull tunables (event detection + metric tiers).

- `bad_set` lists which tiers count as flags (typically `"suboptimal"`).

Gates / thresholds (with defaults if missing):

- `rom_min_delta` (e.g., 40°): if ROM less than this → `"small_rom"` flag.

- `lockout_min_deg` (e.g., 165°): top angle must be ≥ this; else `"no_full_lockout"`.

- `bottom_max_deg` (e.g., 100°): bottom angle must be ≤ this; else `"too_shallow"`.

- `refractory_ms` (e.g., 220 ms): merge spans within this gap.

- Hip checks:

  - `hip_sag_max` (e.g., 0.10 normalized): too large → `"hip_sag"` (or `"pike"` if negative).

  - `hip_amp_ratio` (lo/hi): hip travel vs shoulder travel ratio; outside range → `"hip_travel_mismatch"`.

Event detection parameters:

- `bottom_pct`, `top_pct`: shoulder-Y percentiles (e.g., 0.72/0.28).

- `prom_std`, `width_s`, `min_dist_s`, `dur_min`, `dur_max`: peak finder & pairing.
