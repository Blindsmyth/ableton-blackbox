# Branching Strategy

## Overview

The repository uses a main branch model. All features are developed and tested on the main branch.

## Current Branch: `main`

**Status**: Stable and Production-Ready

The main branch contains all implemented features:

**Core Features:**
- ✅ Drum Rack workflow with 16 pads
- ✅ **Pads Mode sequences** (trigger multiple pads from one sequence)
- ✅ **Keys Mode sequences** (melodic sequences on specific pads)
- ✅ **MIDI Mode sequences** (send MIDI to external devices)
- ✅ Automatic sequence mode detection based on routing
- ✅ Sequence length detection from MIDI clip length
- ✅ Automatic step length adjustment (1/16 default, 1/32 when needed, triplets)
- ✅ Quantised and unquantised sequence support
- ✅ Beat count calculation for clip mode samples
- ✅ Warped sample detection and clip mode
- ✅ Choke group mapping
- ✅ Chain order-based pad mapping
- ✅ Sample envelope extraction
- ✅ Output bus routing
- ✅ Multi-layer sequences (A/B/C/D sub-layers)

**Use this branch for:**
- All production conversions
- All project types (Pads, Keys, MIDI modes)
- Stable, tested functionality

**Installation:**
```bash
git checkout main
git pull origin main
```

---

## Workflow

### For Users

1. **All conversions**: Use `main` branch
2. **Report issues**: Open GitHub issues with project details
3. **Feature requests**: Open GitHub issues or discussions

### For Development

1. **Bug fixes**: Create branches from `main`
2. **New features**: Create branches from `main`
3. **Testing**: Test thoroughly before merging to `main`

---

## Recent Changes

### Latest Version (v2.0)
**Date**: 2025-11-04  
**Branch**: `main`  
**Commit**: `8ec886e`

**Major Features Added:**
- Keys mode sequence support
- MIDI mode sequence support
- Unquantised sequence timing
- Triplet step length detection
- Warped sample detection fix
- Improved sequence mode detection

**Recent Fixes:**
- Fixed warped sample detection (ElementTree truthiness issue)
- Fixed unquantised pads mode (`seqstepmode=0`)
- Fixed unquantised sequence step calculation
- Fixed timing for all sequence modes

---

## Contributing

### Reporting Issues
- Specify Ableton Live version
- Include relevant routing configuration
- Attach sample project if possible
- Describe expected vs actual behavior

### Submitting Improvements
1. Fork the repository
2. Create feature branch from `main`
3. Make changes and test thoroughly
4. Submit pull request with clear description

---

*Last Updated: 2025-11-04*  
*Current Branch: main*  
*All features are on main branch*

