# Sequence Timing and Step Length Workflow

## Overview
This document describes how the converter determines `step_len` and `step_count` for Blackbox sequences, and how it handles quantised vs unquantised MIDI timing.

## Step Length Detection Rules

### Default Behavior
- **Default step_len**: `10` (1/16 notes = 4 steps per beat)
- **Only use finer resolutions** (like 1/32, step_len=14) when notes actually require it

### When to Use 1/32 Resolution (step_len=14)
Only use `step_len=14` (1/32 notes = 8 steps per beat) if:
- Notes fall on 32nd note positions that are **NOT** also 16th note positions
- Examples of positions that require 1/32:
  - 0.125 beats (between 16th notes)
  - 0.375 beats
  - 0.625 beats
  - 0.875 beats
- Notes at 0.0, 0.25, 0.5, 0.75 beats align to both grids → use 1/16

### When to Use Triplet Resolution
If triplets are detected (≥95% aligned to triplet grid and **not mixed with straight notes**):
- Use triplet step_len values:
  - `step_len=11` (1/16T) for 1/16 note triplets (160 ticks = 3 notes per beat)
  - `step_len=9` (1/8T) for 1/8 note triplets (320 ticks = 3 notes per 2 beats)
- Triplet detection takes priority over straight note detection
- **CRITICAL: Mixed triplets + straight notes → ALWAYS treat as unquantised**
  - If both triplet and straight patterns are present (>30% each), sequence must be unquantised
  - This ensures accurate timing when patterns are mixed
  - Mixed patterns cannot be quantised to a single grid, so unquantised mode with precise tick timing is required

### Detection Logic
1. Check if any notes fall on "odd" 32nd note positions (120 ticks but not 240 ticks)
2. If no such notes exist, default to `step_len=10` (1/16)
3. If such notes exist, use `step_len=14` (1/32)

## Step Count Calculation

### Formula
```
step_count = clip_length_beats * steps_per_beat
```

### Steps Per Beat by step_len
- `step_len=14` (1/32): 8 steps per beat
- `step_len=11` (1/16T): 3 steps per beat (triplet) - **preferred when triplets detected**
- `step_len=10` (1/16): 4 steps per beat (default)
- `step_len=9` (1/8T): 1.5 steps per beat (triplet) - **preferred when triplets detected**
- `step_len=8` (1/8): 2 steps per beat

### Step Count Limits
- Maximum: 256 steps
- If calculated step_count > 256, use coarser resolution:
  - Try 1/8 notes (step_len=8)
  - Try 1/4 notes (step_len=6)
  - Continue until step_count ≤ 256

## Quantised vs Unquantised Sequences

### Quantised Sequences
- Use 3840 ticks per beat
- `lencount` > 0 (uses step-based length)
- Step values match the detected `step_len` resolution
- Example: If `step_len=10` (1/16), step values are 0, 4, 8, 12, etc.
- **When to use**: Notes align to a single grid (≥95% alignment) and are either all triplets OR all straight notes

### Unquantised Sequences
- Use 960 ticks per beat (finer resolution for precise timing)
- `lencount=0` (uses precise `lentks` timing)
- Step values still calculated based on `step_len` (default 1/16)
- Example: If `step_len=10` (1/16), step values are 0, 4, 8, 12, etc., but `strtks` values are precise
- **When to use**:
  1. Notes are off-grid (<95% alignment to any grid)
  2. **Mixed triplets + straight notes** (both patterns present >30% each) - **CRITICAL: Always unquantised**
  3. Notes have precise timing that doesn't align to standard grids

## Step Value Calculation

### Critical Rule
**Step values MUST match the step_len resolution**

- If `step_len=14` (1/32): step values = `time_val * 8` (8 steps per beat)
- If `step_len=10` (1/16): step values = `time_val * 4` (4 steps per beat)
- If `step_len=8` (1/8): step values = `time_val * 2` (2 steps per beat)

### Example
For notes at beats 0, 1, 2, 3:
- With `step_len=10` (1/16): steps = 0, 4, 8, 12 ✓
- With `step_len=14` (1/32): steps = 0, 8, 16, 24 ✓
- **WRONG**: `step_len=14` with steps = 0, 4, 8, 12 ✗ (causes 4x speed issue)

## Sequence Location Mapping

### Pads Mode
- Sequence location (row/column) = track index
- `seqpadmapdest` = sequence location pad (where the sequence is placed)
- Example: Track 4 → location pad 4 (row 1, col 0) → `seqpadmapdest="4"`

### Keys Mode
- Sequence location (row/column) = track index (same as Pads mode)
- `seqpadmapdest` = target pad (the pad the sequence plays)
- Example: Track 4 → location pad 4 (row 1, col 0), but plays pad 6 → `seqpadmapdest="6"`

### Critical Rule
**Sequence location ALWAYS matches track index, regardless of mode**
- Track 0 → pad 0 location
- Track 1 → pad 1 location
- Track 4 → pad 4 location
- etc.

## Unquantised Pad Mode Sequences

### Detection
- Notes are detected as unquantised if:
  1. Less than 95% aligned to any grid (off-grid timing)
  2. **Mixed triplet and straight notes** (both patterns present >30% each) - **CRITICAL: Always unquantised**
  3. Notes have precise timing that doesn't align to standard grids

### Handling
- Use 960 ticks per beat (instead of 3840) for finer resolution
- Set `lencount=0` (use precise `lentks` timing instead of step-based length)
- Step values calculated based on `step_len` (default 1/16) for display purposes
- `strtks` and `lentks` use precise tick-based timing
- **Why unquantised for mixed patterns**: Cannot quantise to a single grid when triplets and straight notes are mixed, so precise tick timing is required

## Examples

### Example 1: Simple 16th Note Pattern
- Notes at: 0.0, 1.0, 2.0, 3.0 beats
- Detection: Aligns to 1/16 grid (240 ticks)
- Result: `step_len=10` (1/16), `step_count=16` (4 beats * 4 steps/beat)
- Step values: 0, 4, 8, 12

### Example 2: 32nd Note Pattern
- Notes at: 0.0, 0.125, 0.25, 0.375 beats
- Detection: Has notes at 0.125, 0.375 (require 1/32)
- Result: `step_len=14` (1/32), `step_count=32` (1 beat * 8 steps/beat)
- Step values: 0, 1, 2, 3

### Example 3: Unquantised Pattern (Off-Grid)
- Notes at: 0.0, 0.523, 1.523, 2.523 beats
- Detection: Not aligned to any grid (< 95%)
- Result: `step_len=10` (1/16 default), `lencount=0`, 960 ticks/beat
- Step values: 0, 2, 6, 10 (approximate for display)

### Example 4: Mixed Triplets + Straight Notes (Unquantised)
- Notes at: 0.0, 0.333, 0.5, 0.667, 1.0, 1.25 beats
  - 0.0, 0.5, 1.0, 1.25 = straight 16th notes
  - 0.333, 0.667 = triplet notes
- Detection: Both patterns present (>30% each)
- Result: **Unquantised** (`lencount=0`, 960 ticks/beat), `step_len=10` (1/16 default)
- **Reason**: Cannot quantise to single grid when triplets and straight notes are mixed

## Implementation Notes

1. **Step value recalculation happens AFTER step_len is determined**
2. **Always default to 1/16 unless actual 32nd notes are detected**
3. **Step values must match step_len resolution to avoid tempo issues**
4. **Sequence location always matches track index for correct mapping**
5. **Mixed triplets + straight notes → ALWAYS unquantised** (cannot quantise to single grid)
6. **Triplet detection takes priority** when triplets are well-aligned (≥95%) and not mixed

