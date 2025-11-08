#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ableton Live Drum Rack to 1010music Blackbox converter
Version 0.3 - Drum Rack Workflow

Converts Ableton Live projects with Drum Racks to Blackbox presets.

Based on the original work by Maximilian Karlander (pro424)
Original: https://forum.1010music.com/forum/products/blackbox/support-blackbox/43727-python-script-converting-an-ableton-live-project-to-blackbox-xml

Requirements:
- Track 1: Drum Rack with up to 16 Simplers
- Tracks 2-17: MIDI tracks for sequences (optional)

Features:
- 16-pad drum rack mapping
- Choke group support
- Warped stem detection
- Multi-layer sequences (A/B/C/D)
- Unquantised MIDI timing support
- Compatible with Ableton Live 10, 11, and 12

CREDITS:
- Original author: Maximilian Karlander (pro424) - Blackbox XML format reverse-engineering
- Enhanced by: Simon Schmidt (2024-2025) - Ableton 12 compatibility, Drum Rack workflow
"""
import argparse
from argparse import RawTextHelpFormatter
import xml.etree.ElementTree as ET
import math
import gzip
import os
import shutil
import logging
import sys
import struct

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def get_wav_info(filepath):
    """
    Read WAV file header and return sample information.
    Returns dict with {'sample_length_samples': int, 'sample_rate': int, 'duration_seconds': float}
    Returns None if file doesn't exist or isn't a valid WAV.
    """
    try:
        if not os.path.exists(filepath):
            return None
            
        with open(filepath, 'rb') as f:
            # Read RIFF header
            riff = f.read(4)
            if riff != b'RIFF':
                return None
            
            # Skip file size (4 bytes)
            f.read(4)
            
            # Check for WAVE format
            wave = f.read(4)
            if wave != b'WAVE':
                return None
            
            # Find fmt chunk
            while True:
                chunk_id = f.read(4)
                if not chunk_id:
                    return None
                    
                chunk_size = struct.unpack('<I', f.read(4))[0]
                
                if chunk_id == b'fmt ':
                    # Read fmt chunk
                    audio_format = struct.unpack('<H', f.read(2))[0]  # 1 = PCM
                    num_channels = struct.unpack('<H', f.read(2))[0]
                    sample_rate = struct.unpack('<I', f.read(4))[0]
                    byte_rate = struct.unpack('<I', f.read(4))[0]
                    block_align = struct.unpack('<H', f.read(2))[0]
                    bits_per_sample = struct.unpack('<H', f.read(2))[0]
                    
                    # Skip rest of fmt chunk
                    if chunk_size > 16:
                        f.read(chunk_size - 16)
                    
                    # Find data chunk
                    while True:
                        data_chunk_id = f.read(4)
                        if not data_chunk_id:
                            return None
                        data_chunk_size = struct.unpack('<I', f.read(4))[0]
                        
                        if data_chunk_id == b'data':
                            # Calculate sample length
                            bytes_per_sample = bits_per_sample // 8
                            total_samples = data_chunk_size // (num_channels * bytes_per_sample)
                            duration_seconds = total_samples / sample_rate
                            
                            return {
                                'sample_length_samples': total_samples,
                                'sample_rate': sample_rate,
                                'duration_seconds': duration_seconds,
                                'num_channels': num_channels,
                                'bits_per_sample': bits_per_sample
                            }
                        else:
                            # Skip this chunk
                            f.read(data_chunk_size)
                else:
                    # Skip this chunk
                    f.read(chunk_size)
                    
    except Exception as e:
        logger.debug(f"Error reading WAV file {filepath}: {e}")
        return None


def read_project(file):
    """Read and parse an Ableton Live .als file (handles both gzipped and plain XML)."""
    try:
        # Try to open as gzipped file first
        file_content = gzip.open(file, 'rb')
        tree = ET.parse(file_content)
        root = tree.getroot()
        
        # Log Ableton version info
        version_info = root.attrib
        logger.info(f"Ableton version: {version_info.get('Creator', 'Unknown')}")
        logger.info(f"Major version: {version_info.get('MajorVersion', 'Unknown')}")
        logger.info(f"Minor version: {version_info.get('MinorVersion', 'Unknown')}")
        
        return root
    except OSError as e:
        # If not gzipped, try as regular XML
        if 'Not a gzipped file' in str(e):
            logger.info('File is not gzipped, reading as plain XML')
            tree = ET.parse(file)
            root = tree.getroot()
            
            # Log Ableton version info
            version_info = root.attrib
            logger.info(f"Ableton version: {version_info.get('Creator', 'Unknown')}")
            logger.info(f"Major version: {version_info.get('MajorVersion', 'Unknown')}")
            logger.info(f"Minor version: {version_info.get('MinorVersion', 'Unknown')}")
            
            return root
        else:
            raise
    except Exception as e:
        logger.error(f"Failed to read project file: {e}")
        raise


def find_element_by_tag(parent, tag):
    """Find first child element with given tag."""
    for child in parent:
        if child.tag == tag:
            return child
    return None


def extract_first_midi_note_from_track(midi_track):
    """
    Extract the first MIDI note played in any clip of this MIDI track.
    Used for Keys mode to determine which pad the sequence targets.
    
    Returns:
        int: MIDI note number, or None if no notes found
    """
    try:
        device_chain = find_element_by_tag(midi_track, 'DeviceChain')
        if not device_chain:
            return None
        
        main_sequencer = find_element_by_tag(device_chain, 'MainSequencer')
        if not main_sequencer:
            return None
        
        clip_slot_list = find_element_by_tag(main_sequencer, 'ClipSlotList')
        if not clip_slot_list:
            return None
        
        # Check all clip slots for a MIDI clip
        for clip_slot in list(clip_slot_list):
            if len(clip_slot) > 1:
                clip_slot_value = clip_slot[1]
                if len(clip_slot_value) > 0:
                    midi_clip = clip_slot_value[0][0]
                    notes = midi_clip.find('.//Notes/KeyTracks')
                    if notes and len(notes) > 0:
                        # Get first key track
                        key_track = notes[0]
                        midi_key = find_element_by_tag(key_track, 'MidiKey')
                        if midi_key and 'Value' in midi_key.attrib:
                            return int(midi_key.attrib['Value'])
        
        return None
        
    except Exception as e:
        logger.debug(f'  Error extracting MIDI note: {e}')
        return None


def detect_sequence_mode(midi_track):
    """
    Detect the sequence mode for a MIDI track based on its routing.
    
    Returns:
        tuple: (mode, target)
        - mode: 'Keys', 'MIDI', or 'Pads'
        - target: For Keys mode: branch_id (int), For MIDI mode: channel (int), For Pads mode: None
    
    Routing patterns:
        - Keys Mode: MidiOut/Track.XX/DeviceIn.Y.BZ (routed to specific drum rack pad via Branch Id Z)
        - MIDI Mode: MidiOut/External.Dev:DeviceName/Channel (routed to external MIDI)
        - Pads Mode: MidiOut/Track.XX/TrackIn or MidiOut/None (routed to entire drum rack)
    """
    try:
        # Find MidiOutputRouting/Target element (search recursively)
        midi_output_routing = midi_track.find('.//MidiOutputRouting')
        if midi_output_routing is None:
            logger.debug('  No MidiOutputRouting found, defaulting to Pads mode')
            return 'Pads', None
        
        target_elem = find_element_by_tag(midi_output_routing, 'Target')
        if target_elem is None or 'Value' not in target_elem.attrib:
            logger.debug('  No routing Target found, defaulting to Pads mode')
            return 'Pads', None
        
        target = target_elem.attrib['Value']
        logger.debug(f'  Routing target: {target}')
        
        # Check for Keys mode: MidiOut/Track.XX/DeviceIn.Y.BZ,W.V
        # Example: MidiOut/Track.34/DeviceIn.0.B40,0.0
        # The BZ part (e.g., B40) is the Branch Id that maps to a specific pad
        if '/DeviceIn.' in target:
            # Extract the DeviceIn part
            device_part = target.split('/DeviceIn.')[-1]
            
            # Parse format: 0.B40,0.0
            # Split by periods
            parts = device_part.split('.')
            if len(parts) >= 2:
                second_part = parts[1]
                
                # Check if second part contains 'B' followed by a number (Branch Id)
                if 'B' in second_part:
                    branch_part = second_part.split(',')[0]  # Get part before comma
                    if branch_part.startswith('B'):
                        try:
                            branch_id = int(branch_part[1:])  # Remove 'B' prefix and convert to int
                            logger.info(f'  Detected Keys mode → Branch Id {branch_id}')
                            return 'Keys', branch_id
                        except ValueError:
                            logger.warning(f'  Could not parse branch id from: {branch_part}')
            
            # Fallback: use chain index
            try:
                chain_index = int(device_part.split('.')[0])
                logger.info(f'  Detected Keys mode → Chain index {chain_index} (fallback)')
                return 'Keys', chain_index
            except ValueError:
                logger.warning(f'  Could not parse chain index from: {device_part}')
                return 'Pads', None
        
        # Check for MIDI mode: MidiOut/External.Dev:
        if '/External.Dev:' in target or '/External/' in target:
            # Extract MIDI channel if present (usually ends with /Channel)
            channel = 0  # Default to channel 0 (Ch1)
            if '/' in target:
                parts = target.split('/')
                if parts[-1].isdigit():
                    channel = int(parts[-1])
            logger.info(f'  Detected MIDI mode → Channel {channel}')
            return 'MIDI', channel
        
        # Default to Pads mode (TrackIn or None)
        logger.debug('  Defaulting to Pads mode')
        return 'Pads', None
        
    except Exception as e:
        logger.warning(f'  Error detecting sequence mode: {e}, defaulting to Pads mode')
        return 'Pads', None


def find_tempo(root):
    """
    Find tempo in the project using tag-based navigation.
    Works with both Ableton 10 (MasterTrack) and 12 (MainTrack).
    """
    try:
        liveset = root[0]
        
        # Try MainTrack first (Live 12+)
        maintrack = find_element_by_tag(liveset, 'MainTrack')
        
        # Fall back to MasterTrack (Live 10/11)
        if maintrack is None:
            maintrack = find_element_by_tag(liveset, 'MasterTrack')
        
        if maintrack is None:
            logger.warning("Could not find MainTrack or MasterTrack")
            return '120'  # Default tempo
        
        # Navigate: MainTrack -> DeviceChain -> Mixer -> Tempo -> Manual
        device_chain = find_element_by_tag(maintrack, 'DeviceChain')
        if device_chain is None:
            logger.warning("Could not find DeviceChain")
            return '120'
        
        mixer = find_element_by_tag(device_chain, 'Mixer')
        if mixer is None:
            logger.warning("Could not find Mixer")
            return '120'
        
        tempo_elem = find_element_by_tag(mixer, 'Tempo')
        if tempo_elem is None:
            logger.warning("Could not find Tempo element")
            return '120'
        
        manual = find_element_by_tag(tempo_elem, 'Manual')
        if manual is None or 'Value' not in manual.attrib:
            logger.warning("Could not find Manual tempo value")
            return '120'
        
        tempo = manual.attrib['Value']
        logger.info(f"Found tempo: {tempo} BPM")
        return tempo
        
    except Exception as e:
        logger.warning(f"Error finding tempo: {e}. Using default 120 BPM")
        return '120'


def find_tracks(root):
    """Find the Tracks element in the project."""
    try:
        liveset = root[0]
        tracks = find_element_by_tag(liveset, 'Tracks')
        
        if tracks is None:
            logger.error("Could not find Tracks element")
            return None
        
        logger.info(f"Found {len(tracks)} tracks")
        return tracks
        
    except Exception as e:
        logger.error(f"Error finding tracks: {e}")
        return None


def track_tempo_extractor(root):
    """Extract tracks and tempo from the project."""
    tracks = find_tracks(root)
    tempo = find_tempo(root)
    
    if tracks is None:
        raise ValueError("Could not extract tracks from project")
    
    return tracks, tempo


def device_extract(track, track_count):
    """Extract device information from a track."""
    device_dict = {}
    logger.info(f'Track {track_count}, track type: {track.tag}')
    
    try:
        device_chain = find_element_by_tag(track, 'DeviceChain')
        if device_chain is None:
            return device_dict, track.tag
        
        # Find the nested DeviceChain
        nested_chain = find_element_by_tag(device_chain, 'DeviceChain')
        if nested_chain is None:
            return device_dict, track.tag
        
        # Find Devices element
        devices_elem = find_element_by_tag(nested_chain, 'Devices')
        if devices_elem is None:
            return device_dict, track.tag
        
        # Extract individual devices
        count = 1
        for device in devices_elem:
            logger.info(f'  Device {count}: {device.tag}')
            count += 1
            device_dict[device.tag] = device
            
    except Exception as e:
        logger.warning(f"Error extracting devices from track {track_count}: {e}")
    
    return device_dict, track.tag


def safe_navigate(element, path_description, *indices_or_tags):
    """
    Safely navigate XML tree using indices or tags.
    Returns None if path doesn't exist.
    
    Args:
        element: Starting element
        path_description: Description for error messages
        *indices_or_tags: Mix of integer indices or string tag names
    """
    current = element
    path = []
    
    try:
        for item in indices_or_tags:
            if isinstance(item, int):
                if len(current) <= item:
                    logger.warning(f"Path {path_description}: Index {item} out of range (length {len(current)})")
                    return None
                current = current[item]
                path.append(f"[{item}]")
            elif isinstance(item, str):
                found = find_element_by_tag(current, item)
                if found is None:
                    logger.warning(f"Path {path_description}: Tag '{item}' not found")
                    return None
                current = found
                path.append(f"<{item}>")
        return current
    except Exception as e:
        logger.warning(f"Error navigating {path_description} at {''.join(path)}: {e}")
        return None


def drum_rack_extract(drum_rack_device):
    """
    Extract all Simplers from a DrumGroupDevice.
    Returns a list of pad info: [{'blackbox_pad': 0-15, 'simpler': device, 'midi_note': 36-51, 'choke_group': 0-16, 'branch_id': X, 'name': '...'}, ...]
    """
    pad_list = []
    
    try:
        # Find Branches element
        branches = find_element_by_tag(drum_rack_device, 'Branches')
        if not branches:
            logger.warning("DrumGroupDevice has no Branches element")
            return pad_list
        
        # Extract pads from branches
        # Map branch/chain index to Blackbox pad
        # Default: Use chain order as pad order (Branch 0 = Pad 0, etc.)
        # Blackbox has 16 pads in a 4x4 grid
        max_pads = 16
        for branch_index in range(min(len(branches), max_pads)):
            branch = branches[branch_index]
            
            # Extract branch Id attribute (used for Keys mode routing)
            branch_id = branch.attrib.get('Id', None)
            if branch_id:
                try:
                    branch_id = int(branch_id)
                except ValueError:
                    branch_id = None
            
            pad_info = {
                'blackbox_pad': branch_index,  # Use chain index as pad index by default (0-15)
                'simpler': None,
                'midi_note': None,
                'choke_group': 0,
                'branch_id': branch_id,  # Store branch Id for Keys mode pad mapping
                'name': '',
                'is_empty': True
            }
            
            # Extract BranchInfo for MIDI note and choke group
            branch_info = find_element_by_tag(branch, 'BranchInfo')
            if branch_info:
                receiving_note = find_element_by_tag(branch_info, 'ReceivingNote')
                if receiving_note and 'Value' in receiving_note.attrib:
                    midi_note = int(receiving_note.attrib['Value'])
                    pad_info['midi_note'] = midi_note
                
                choke_group = find_element_by_tag(branch_info, 'ChokeGroup')
                logger.debug(f'  Branch {branch_index}: ChokeGroup element found: {choke_group is not None}')
                if choke_group is not None:
                    logger.debug(f'    ChokeGroup attribs: {choke_group.attrib}')
                    if 'Value' in choke_group.attrib:
                        # Ableton choke group mapping to Blackbox excl groups:
                        # Ableton 0 or -1 (no choke) → Blackbox 0 (excl group X)
                        # Ableton 1-4 → Blackbox 1-4 (excl groups A-D)
                        ableton_choke = int(choke_group.attrib['Value'])
                        logger.debug(f'    Ableton choke value: {ableton_choke}')
                        if ableton_choke <= 0:
                            pad_info['choke_group'] = 0  # No choke / excl group X
                        elif ableton_choke >= 1 and ableton_choke <= 4:
                            pad_info['choke_group'] = ableton_choke  # Direct mapping for groups 1-4 (A-D)
                            logger.debug(f'    → Mapped to Blackbox choke group: {ableton_choke}')
                        else:
                            # If Ableton has choke groups > 4, cap at 4 (excl group D)
                            pad_info['choke_group'] = min(ableton_choke, 4)
                            logger.debug(f'    → Capped to Blackbox choke group: {pad_info["choke_group"]}')
                    else:
                        logger.debug(f'    ChokeGroup has no Value attribute')
                else:
                    logger.debug(f'  Branch {branch_index}: No ChokeGroup element found in BranchInfo')
            
            # Extract Name
            name_elem = find_element_by_tag(branch, 'Name')
            if name_elem and 'Value' in name_elem.attrib:
                pad_info['name'] = name_elem.attrib['Value']
            
            # Extract Simpler device from DeviceChain
            dev_chain = find_element_by_tag(branch, 'DeviceChain')
            if dev_chain:
                # Check for MidiToAudioDeviceChain (Ableton 12.3+)
                midi_to_audio = find_element_by_tag(dev_chain, 'MidiToAudioDeviceChain')
                if midi_to_audio:
                    devices_elem = find_element_by_tag(midi_to_audio, 'Devices')
                else:
                    # Fallback to direct Devices (older structure)
                    devices_elem = find_element_by_tag(dev_chain, 'Devices')
                
                if devices_elem:
                    simpler = find_element_by_tag(devices_elem, 'OriginalSimpler')
                    if simpler:
                        pad_info['simpler'] = simpler
                        pad_info['is_empty'] = False
            
            # Only add pads that have a valid pad number
            if pad_info['blackbox_pad'] is not None:
                pad_list.append(pad_info)
                
                # Log pad mapping
                choke_label = {0: 'X (none)', 1: 'A', 2: 'B', 3: 'C', 4: 'D'}.get(pad_info["choke_group"], str(pad_info["choke_group"]))
                logger.info(f'  Chain {branch_index} → Pad {pad_info["blackbox_pad"]}: MIDI {pad_info["midi_note"]}, Choke: {choke_label}, Has Simpler: {not pad_info["is_empty"]}')
            else:
                logger.debug(f'  Chain {branch_index}: Skipped (no valid pad number)')
        
        # Keep pads in chain order (don't sort - preserve the order they appear in Ableton)
        # This ensures the visual layout matches what the user sees in Ableton
        
        logger.info(f'Extracted {len(pad_list)} drum rack pads')
        return pad_list
        
    except Exception as e:
        logger.error(f"Error extracting drum rack: {e}")
        import traceback
        traceback.print_exc()
        return pad_list


def detect_warped_stem(device):
    """
    Detect if a Simpler contains a warped stem sample.
    Returns dict with {'is_warped': bool, 'beat_count': int, 'loop_length_bars': float, 'trigger_mode': str}
    """
    result = {
        'is_warped': False,
        'beat_count': 0,
        'loop_length_bars': 0.0,
        'trigger_mode': 'gate'  # default
    }
    
    logger.debug('detect_warped_stem: Starting detection')
    try:
        # Extract trigger mode from Simpler (1-shot vs classic)
        # TriggerMode: 0=Gate, 1=Trigger(1-shot), 2=Toggle
        player = find_element_by_tag(device, 'Player')
        if player:
            trigger_mode_elem = find_element_by_tag(player, 'TriggerMode')
            if trigger_mode_elem and 'Value' in trigger_mode_elem.attrib:
                trigger_val = int(trigger_mode_elem.attrib['Value'])
                if trigger_val == 0:
                    result['trigger_mode'] = 'gate'
                elif trigger_val == 1:
                    result['trigger_mode'] = 'trigger'
                elif trigger_val == 2:
                    result['trigger_mode'] = 'toggle'
        
            # Check for warp properties in the sample
            player = safe_navigate(device, "Player", 19)
            if not player:
                player = find_element_by_tag(device, 'Player')
            if not player:
                logger.debug('  detect_warped_stem: No Player found')
                return result
            
            multi_sample_map = find_element_by_tag(player, 'MultiSampleMap')
            if not multi_sample_map:
                logger.debug('  detect_warped_stem: No MultiSampleMap found')
                return result
            
            sample_parts = find_element_by_tag(multi_sample_map, 'SampleParts')
            if not sample_parts or len(sample_parts) == 0:
                logger.debug('  detect_warped_stem: No SampleParts found')
                return result
            
            part = sample_parts[0]
            logger.debug(f'  detect_warped_stem: Found SamplePart')
            
            # Check for SampleWarpProperties
            warp_props = find_element_by_tag(part, 'SampleWarpProperties')
            if warp_props:
                logger.debug('  detect_warped_stem: Found SampleWarpProperties!')
                
                # Check both WarpMode and IsWarped flag
                warp_mode = find_element_by_tag(warp_props, 'WarpMode')
                is_warped_elem = find_element_by_tag(warp_props, 'IsWarped')
                
                warp_mode_val = 0
                is_warped_val = False
                
                if warp_mode and 'Value' in warp_mode.attrib:
                    warp_mode_val = int(warp_mode.attrib['Value'])
                    logger.info(f'  detect_warped_stem: WarpMode = {warp_mode_val}')
                
                if is_warped_elem and 'Value' in is_warped_elem.attrib:
                    is_warped_str = is_warped_elem.attrib['Value']
                    is_warped_val = is_warped_str.lower() == 'true'
                    logger.info(f'  detect_warped_stem: IsWarped = "{is_warped_str}" → {is_warped_val}')
                
                # Try to extract loop length from LoopLength element
                # First check in SampleWarpProperties
                loop_length_elem = find_element_by_tag(warp_props, 'LoopLength')
                if not loop_length_elem:
                    # Try in part level
                    loop_length_elem = find_element_by_tag(part, 'LoopLength')
                
                if loop_length_elem and 'Value' in loop_length_elem.attrib:
                    loop_length_beats = float(loop_length_elem.attrib['Value'])
                    result['loop_length_bars'] = loop_length_beats / 4.0
                    result['beat_count'] = int(loop_length_beats)
                    logger.debug(f'  detect_warped_stem: Found LoopLength: {loop_length_beats} beats')
                
                # Always extract sample duration from SampleRef (for beat calculation)
                sample_ref = find_element_by_tag(part, 'SampleRef')
                logger.debug(f'  detect_warped_stem: Looking for SampleRef... found: {sample_ref is not None}')
                if sample_ref:
                    default_duration_elem = find_element_by_tag(sample_ref, 'DefaultDuration')
                    default_sample_rate_elem = find_element_by_tag(sample_ref, 'DefaultSampleRate')
                    logger.debug(f'  detect_warped_stem: DefaultDuration: {default_duration_elem is not None}, DefaultSampleRate: {default_sample_rate_elem is not None}')
                    logger.debug(f'  detect_warped_stem: Bool test - dur: {bool(default_duration_elem)}, rate: {bool(default_sample_rate_elem)}, and: {bool(default_duration_elem and default_sample_rate_elem)}')
                    
                    if default_duration_elem is not None and default_sample_rate_elem is not None:
                        logger.debug(f'  detect_warped_stem: About to extract duration values...')
                        try:
                            dur_val = default_duration_elem.attrib.get('Value')
                            rate_val = default_sample_rate_elem.attrib.get('Value')
                            logger.debug(f'  detect_warped_stem: Raw values - Duration: {dur_val}, SampleRate: {rate_val}')
                            
                            duration_samples = float(dur_val) if dur_val else 0
                            sample_rate = float(rate_val) if rate_val else 48000
                            logger.debug(f'  detect_warped_stem: Extracted values: {duration_samples} samples @ {sample_rate}Hz')
                            
                            if duration_samples > 0 and sample_rate > 0:
                                duration_seconds = duration_samples / sample_rate
                                result['sample_duration_seconds'] = duration_seconds
                                logger.info(f'  ✓ Sample duration: {duration_seconds:.2f}s = {duration_samples} samples @ {sample_rate}Hz')
                        except (ValueError, TypeError) as e:
                            logger.warning(f'  detect_warped_stem: Error extracting duration: {e}')
                
                # Sample is warped if WarpMode > 0 OR IsWarped = true
                if warp_mode_val > 0 or is_warped_val:
                    result['is_warped'] = True
                    logger.info(f'  ✓ Sample IS WARPED (WarpMode={warp_mode_val}, IsWarped={is_warped_val})')
                else:
                    logger.info(f'  ✗ Sample NOT warped (WarpMode={warp_mode_val}, IsWarped={is_warped_val})')
            else:
                logger.debug('  detect_warped_stem: No SampleWarpProperties found')
        
        # If we can't determine from warp properties, check if it's a long sample
        # (stems are typically longer than one-shots)
        # This is a heuristic fallback
        
        return result
        
    except Exception as e:
        logger.warning(f"Error detecting warped stem: {e}")
        return result


def sampler_extract(device):
    """Extract sampler/simpler parameters with robust error handling."""
    params = {}
    
    try:
        # Live 12.2+ structure: Use tag-based navigation for Player element
        # Try Live 12.2+ path first (works for 12.2, 12.3+)
        player = find_element_by_tag(device, 'Player')
        sample_map = None
        
        if player:
            multi_sample_map = find_element_by_tag(player, 'MultiSampleMap')
            if multi_sample_map:
                sample_parts = find_element_by_tag(multi_sample_map, 'SampleParts')
                if sample_parts and len(sample_parts) > 0:
                    # In Live 12.2+, SampleParts contains MultiSamplePart elements
                    # We'll iterate through SampleParts (which is the container)
                    sample_map = sample_parts
                    logger.info("  Found Live 12.2+ structure")
        
        # Fallback to older Live 10/11 structure
        if sample_map is None:
            sample_map = safe_navigate(device, "MultiSampleMap", 15, 0, 0)
            if sample_map:
                logger.info("  Found Live 10/11 structure")
        
        if sample_map is None:
            logger.warning("Could not find sample map in device")
            return None
        
        # Extract multisample parts
        sample_names = []
        filepaths = []
        rootkeys = []
        keyrangemins = []
        keyrangemaxs = []
        
        # Check if this is Live 12.2+ structure (SampleParts contains MultiSamplePart)
        if sample_map.tag == 'SampleParts':
            # Live 12.2+ structure - iterate through all children
            for i in range(len(sample_map)):
                part = sample_map[i]
                
                # Skip if not a MultiSamplePart
                if part.tag != 'MultiSamplePart':
                    continue
                
                # Find SampleRef in this part using tag-based search
                sample_ref = None
                for child in part:
                    if child.tag == 'SampleRef':
                        sample_ref = child
                        logger.info(f'  Found SampleRef in MultiSamplePart[{i}]')
                        break
                
                if sample_ref is None:
                    logger.warning(f'  No SampleRef found in MultiSamplePart[{i}]')
                    continue
                
                # Live 12.2+ uses FileRef with Path element
                file_ref = None
                for child in sample_ref:
                    if child.tag == 'FileRef':
                        file_ref = child
                        logger.info(f'  Found FileRef')
                        break
                
                if file_ref:
                    # Look for Path element using tag-based search (prefer absolute Path over RelativePath)
                    path_elem = None
                    rel_path_elem = None
                    for child in file_ref:
                        if child.tag == 'Path':
                            if 'Value' in child.attrib:
                                path_elem = child
                                logger.info(f'  Found Path element')
                        elif child.tag == 'RelativePath':
                            if 'Value' in child.attrib:
                                rel_path_elem = child
                                logger.info(f'  Found RelativePath element')
                    
                    if path_elem is not None:
                        logger.info(f'  Entering path_elem block')
                        try:
                            full_path = path_elem.attrib['Value']
                            logger.info(f'  Got path value: {full_path[:50]}...')
                            filepaths.append(full_path)
                            sample_name = full_path.split('/')[-1]
                            sample_names.append(sample_name)
                            logger.info(f'  Found sample: {sample_name}')
                            logger.info(f'  Full path: {full_path}')
                        except Exception as e:
                            logger.warning(f'  Error extracting Path value: {e}')
                            import traceback
                            traceback.print_exc()
                            path_elem = None  # Reset so we can try RelativePath
                    
                    if path_elem is None and rel_path_elem is not None:
                        try:
                            rel_path_value = rel_path_elem.attrib['Value']
                            filepaths.append(rel_path_value)
                            sample_name = rel_path_value.split('/')[-1]
                            sample_names.append(sample_name)
                            logger.info(f'  Found sample (relative): {sample_name}')
                            logger.info(f'  Relative path: {rel_path_value}')
                        except Exception as e:
                            logger.warning(f'  Error extracting RelativePath value: {e}')
                    
                    if path_elem is None and rel_path_elem is None:
                        logger.warning(f'  Could not find Path or RelativePath in FileRef')
                        continue
                    
                    if len(filepaths) == 0:
                        continue
                else:
                    logger.warning(f'  No FileRef found in SampleRef')
                    continue
                
                # Get root key for Live 12.2+
                root_key = safe_navigate(part, "RootKey", 8)
                if root_key and 'Value' in root_key.attrib:
                    rootkeys.append(root_key.attrib['Value'])
                    logger.info(f'  Root key: {root_key.attrib["Value"]}')
                else:
                    rootkeys.append('60')  # Default middle C
                
                # Get key range for Live 12.2+
                key_range = safe_navigate(part, "KeyRange", 5)
                if key_range:
                    key_min = safe_navigate(key_range, "KeyRangeMin", 0)
                    key_max = safe_navigate(key_range, "KeyRangeMax", 1)
                    
                    if key_min and 'Value' in key_min.attrib:
                        keyrangemins.append(key_min.attrib['Value'])
                    else:
                        keyrangemins.append('0')
                    
                    if key_max and 'Value' in key_max.attrib:
                        keyrangemaxs.append(key_max.attrib['Value'])
                    else:
                        keyrangemaxs.append('127')
                    
                    logger.info(f'  Key range: {keyrangemins[-1]} - {keyrangemaxs[-1]}')
                else:
                    keyrangemins.append('0')
                    keyrangemaxs.append('127')
        else:
            # Live 10/11 structure (old path)
            for i in range(len(sample_map)):
                part = sample_map[i]
                
                # Try to find sample reference
                sample_ref = safe_navigate(part, "SampleRef", 18, 0)
                if sample_ref is None:
                    continue
                
                # Get file name
                file_ref = safe_navigate(sample_ref, "FileName", 3)
                if file_ref and 'Value' in file_ref.attrib:
                    sample_name = file_ref.attrib['Value']
                    sample_names.append(sample_name)
                else:
                    continue
                
                # Get file path
                path_hint = safe_navigate(sample_ref, "PathHint", 7, 0)
                if path_hint:
                    filepath = ''
                    for k in range(len(path_hint)):
                        if 'Dir' in path_hint[k].attrib:
                            filepath = filepath + '/' + path_hint[k].attrib['Dir']
                    filepaths.append(filepath + '/' + sample_name)
                else:
                    filepaths.append(sample_name)
            
            # Get root key
            root_key = safe_navigate(part, "RootKey", 8)
            if root_key and 'Value' in root_key.attrib:
                rootkeys.append(root_key.attrib['Value'])
                logger.info(f'  Root key: {root_key.attrib["Value"]}')
            else:
                rootkeys.append('60')  # Default middle C
            
            # Get key range
            key_range = safe_navigate(part, "KeyRange", 5)
            if key_range:
                key_min = safe_navigate(key_range, "KeyRangeMin", 0)
                key_max = safe_navigate(key_range, "KeyRangeMax", 1)
                
                if key_min and 'Value' in key_min.attrib:
                    keyrangemins.append(key_min.attrib['Value'])
                else:
                    keyrangemins.append('0')
                
                if key_max and 'Value' in key_max.attrib:
                    keyrangemaxs.append(key_max.attrib['Value'])
                else:
                    keyrangemaxs.append('127')
                
                logger.info(f'  Key range: {keyrangemins[-1]} - {keyrangemaxs[-1]}')
            else:
                keyrangemins.append('0')
                keyrangemaxs.append('127')
        
        if not filepaths:
            logger.warning("No samples found in device")
            return None
        
        params['filepath'] = filepaths
        params['rootkey'] = rootkeys
        params['keyrangemin'] = keyrangemins
        params['keyrangemax'] = keyrangemaxs
        
        if not filepaths:
            logger.warning("No samples found in device")
            return None
        
        params['filepath'] = filepaths
        params['rootkey'] = rootkeys
        params['keyrangemin'] = keyrangemins
        params['keyrangemax'] = keyrangemaxs
        
        logger.info(f'  Sample names: {sample_names}')
        logger.info(f'  Sample filepaths: {filepaths}')
        
        # Store with both key names for compatibility
        params['filepaths'] = filepaths
        params['rootkeys'] = rootkeys
        params['keyrangemins'] = keyrangemins
        params['keyrangemaxs'] = keyrangemaxs
        
        # Find sample start and end points
        if sample_map.tag == 'SampleParts' and len(sample_map) > 0:
            # Live 12.2+ structure
            first_part = sample_map[0]
        else:
            first_part = sample_map[0]
        
        sample_start = None
        sample_end = None
        for child in first_part:
            if child.tag == 'SampleStart' and 'Value' in child.attrib:
                sample_start = child
            if child.tag == 'SampleEnd' and 'Value' in child.attrib:
                sample_end = child
        
        if sample_start:
            params['sample_start'] = sample_start.attrib['Value']
        else:
            params['sample_start'] = '0'
        
        if sample_end:
            params['sample_end'] = sample_end.attrib['Value']
        else:
            params['sample_end'] = '44100'  # Default 1 second at 44.1kHz
        
        logger.info(f'  Play start: {params["sample_start"]}')
        logger.info(f'  Play end: {params["sample_end"]}')
        
        # Find loop settings
        loop_on = None
        loop_start = None
        loop_end = None
        
        for child in first_part:
            if child.tag == 'LoopOn' and 'Value' in child.attrib:
                loop_on = child
            if child.tag == 'LoopStart' and 'Value' in child.attrib:
                loop_start = child
            if child.tag == 'LoopEnd' and 'Value' in child.attrib:
                loop_end = child
        
        if loop_on:
            params['loop_on'] = loop_on.attrib['Value']
        else:
            params['loop_on'] = '0'  # Default off
        
        if loop_start:
            params['loop_start'] = loop_start.attrib['Value']
        else:
            params['loop_start'] = '0'
        
        if loop_end:
            params['loop_end'] = loop_end.attrib['Value']
        else:
            params['loop_end'] = params.get('sample_end', '44100')
        
        logger.info(f'  Loop On: {params["loop_on"]}')
        logger.info(f'  Loop Start: {params["loop_start"]}')
        logger.info(f'  Loop End: {params["loop_end"]}')
        
        # Find envelope settings
        # Try to locate the amplitude envelope
        envelope = safe_navigate(device, "VolumeEnvelope", 19, 8)
        
        if envelope:
            attack = safe_navigate(envelope, "Attack", 0, 1)
            decay = safe_navigate(envelope, "Decay", 3, 1)
            sustain = safe_navigate(envelope, "Sustain", 6, 1)
            release = safe_navigate(envelope, "Release", 7, 1)
            
            params['attack'] = attack.attrib.get('Value', '1') if attack else '1'
            params['decay'] = decay.attrib.get('Value', '300') if decay else '300'
            params['sustain'] = sustain.attrib.get('Value', '1') if sustain else '1'
            params['release'] = release.attrib.get('Value', '200') if release else '200'
        else:
            # Default envelope values
            params['attack'] = '1'
            params['decay'] = '300'
            params['sustain'] = '1'
            params['release'] = '200'
        
        logger.info(f'  Vol Env Attack: {round(float(params["attack"]))} ms')
        logger.info(f'  Vol Env Decay: {round(float(params["decay"]))} ms')
        logger.info(f'  Vol Env Sustain: {round(8.6859*math.log(max(float(params["sustain"]), 0.001)))} dB')
        logger.info(f'  Vol Env Release: {round(float(params["release"]))} ms')
        
        return params
        
    except Exception as e:
        logger.error(f"Error extracting sampler parameters: {e}")
        import traceback
        traceback.print_exc()
        return None


def track_iterator(tracks):
    """
    Extract drum rack and MIDI tracks from Ableton project.
    Returns: (pad_list, midi_tracks)
    
    Expected structure:
    - Track 1: Drum Rack with 16 pads
    - Tracks 2-17: MIDI tracks for sequences
    """
    if len(tracks) == 0:
        logger.error('No tracks found in project')
        return [], []
    
    # First track should contain DrumGroupDevice
    first_track = tracks[0]
    devices, track_type = device_extract(first_track, 1)
    
    if 'DrumGroupDevice' not in devices:
        logger.error('ERROR: No DrumGroupDevice found in first track!')
        logger.error('This script requires a Drum Rack in the first track.')
        logger.error('Please set up your project with:')
        logger.error('  - Track 1: Drum Rack with up to 16 Simplers')
        logger.error('  - Tracks 2-17: MIDI tracks for sequences')
        return [], []
    
    logger.info('='*60)
    logger.info('DRUM RACK DETECTED')
    logger.info('='*60)
    logger.warning('NOTE: Pad mapping uses CHAIN ORDER, not MIDI notes!')
    logger.warning('Ensure chains are ordered correctly in Ableton before converting.')
    logger.warning('Chain 0 → Pad 0, Chain 1 → Pad 1, etc.')
    logger.info('='*60)
    
    # Extract drum rack pads
    drum_rack = devices['DrumGroupDevice']
    pad_list = drum_rack_extract(drum_rack)
    
    # Collect MIDI tracks (tracks 2-17 should be the 16 MIDI tracks)
    # Support both: numbered tracks (tracks 2-17) and named tracks (e.g., "Seq1", "Seq2", etc.)
    midi_tracks = []
    midi_track_info = []  # Store (track, name, index) tuples
    for i in range(1, min(17, len(tracks))):
        track = tracks[i]
        devices_check, track_type_check = device_extract(track, i+1)
        if track_type_check == 'MidiTrack':
            # Extract track name
            name_elem = find_element_by_tag(track, 'Name')
            track_name = name_elem.attrib.get('Value', '') if name_elem is not None else ''
            midi_tracks.append(track)
            midi_track_info.append((track, track_name, len(midi_tracks)-1))
            logger.info(f'  Found MIDI track {i+1} (name="{track_name}") for sequence (midi_tracks index {len(midi_tracks)-1})')
    
    logger.info(f'Extracted {len(pad_list)} drum pads and {len(midi_tracks)} MIDI tracks')
    return pad_list, midi_tracks, midi_track_info


# Helper functions for generating Blackbox XML

def row_column(pad):
    rc_dict = {0:[0,0], 1:[0,1], 2:[0,2], 3:[0,3],
               4:[1,0], 5:[1,1], 6:[1,2], 7:[1,3],
               8:[2,0], 9:[2,1], 10:[2,2], 11:[2,3],
               12:[3,0], 13:[3,1], 14:[3,2], 15:[3,3],
               16:[0,4], 17:[1,4], 18:[2,4], 19:[3,4]}
    rc = rc_dict[int(pad)]
    row = rc[0]
    column = rc[1]
    return(row, column)

def pad_dicter(row, column, filename, type):
    cell_dict = {'row':str(row), 'column':str(column), 'layer':"0", 'filename':filename, 'type':type}
    return(cell_dict)

def pad_params_dicter(envattack, envdecay, envsus, envrel, samstart, samlen, multisammode, loopmode, loopstart, loopend, beatcount, samtrigtype, cellmode, polymode):
    params_dict = {'gaindb': '0', 'pitch': '0', 'panpos': '0', 'samtrigtype': str(samtrigtype), 'loopmode': str(loopmode), 
                    'loopmodes': '0', 'midimode': '0', 'midioutchan': '0', 'reverse': '0', 'cellmode': str(cellmode), 
                    'envattack': str(envattack), 'envdecay': str(envdecay), 'envsus': str(envsus), 
                    'envrel': str(envrel), 'samstart': str(samstart), 'samlen': str(samlen), 'loopstart': str(loopstart), 
                    'loopend': str(loopend), 'quantsize': '3', 'synctype': '5', 'actslice': '1', 'outputbus': '0', 
                    'polymode': str(polymode), 'polymodeslice': '0', 'slicestepmode': '0', 'chokegrp': '0', 'dualfilcutoff': '0', 
                    'res': '500', 'rootnote': '0', 'beatcount': str(beatcount), 'fx1send': '0', 'fx2send': '0', 'multisammode': multisammode, 
                    'interpqual': '0', 'playthru': '0', 'slicerquantsize': '13', 'slicersync': '0', 'padnote': '0', 
                    'loopfadeamt': '0', 'lfowave': '0', 'lforate': '100', 'lfoamount': '1000', 'lfokeytrig': '0', 'lfobeatsync': '0', 
                    'lforatebeatsync': '0', 'grainsizeperc': '300', 'grainscat': '0', 'grainpanrnd': '0', 'graindensity': '600', 
                    'slicemode': '0', 'legatomode': '0', 'gainssrcwin': '0', 'grainreadspeed': '1000', 'recpresetlen': '0', 
                    'recquant': '3', 'recinput': '0', 'recinputmulti': '0', 'recusethres': '0', 'recthresh': '-20000', 'recmonoutbus': '0'}
    return(params_dict)

def make_drum_rack_pads(session, pad_list, tempo):
    """
    Create Blackbox pads from Drum Rack pad list.
    Each pad in pad_list contains: {'blackbox_pad': 0-15, 'simpler': device, 'choke_group': 0-16, ...}
    """
    # Convert tempo to float (it comes as a string from track_tempo_extractor)
    try:
        tempo = float(tempo)
    except (ValueError, TypeError):
        logger.warning(f'Invalid tempo value: {tempo}, using 120 BPM')
        tempo = 120.0
    
    assets = []
    
    for pad_info in pad_list:
        pad_num = pad_info['blackbox_pad']
        row, column = row_column(pad_num)
        
        if not pad_info['is_empty'] and pad_info['simpler']:
            # Extract sample parameters from Simpler
            params = sampler_extract(pad_info['simpler'])
            
            if params is None:
                # Sample extraction failed, treat as empty pad
                logger.warning(f'  Pad {pad_num}: Sample extraction failed, creating empty pad')
                cell = ET.SubElement(session, 'cell')
                cell.attrib = pad_dicter(row, column, '', 'samtempl')
                param_elem = ET.SubElement(cell, 'params')
                param_elem.attrib = pad_params_dicter('0', '0', '1000', '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')
                param_elem.attrib['chokegrp'] = '0'
            else:
                # Get sample filename and create proper cell
                sample_filename = params.get('filepaths', [''])[0].split('/')[-1] if params.get('filepaths') else ''
                logger.info(f'  Pad {pad_num}: {sample_filename}')
                
                # Create cell with filename
                filename_path = '.\\' + sample_filename if sample_filename else ''
                cell = ET.SubElement(session, 'cell')
                cell.attrib = pad_dicter(row, column, filename_path, 'sample')
                
                # Get WAV file info for sample length
                filepath = params.get('filepaths', [''])[0] if params.get('filepaths') else ''
                wav_info = get_wav_info(filepath) if filepath else None
                
                # Set sample length from WAV file
                samlen = '0'
                if wav_info:
                    samlen = str(wav_info['sample_length_samples'])
                    logger.debug(f'    WAV info: {wav_info["sample_length_samples"]} samples, {wav_info["duration_seconds"]:.2f}s @ {wav_info["sample_rate"]}Hz')
                
                # Check if this is a warped stem
                warp_info = detect_warped_stem(pad_info['simpler'])
                
                # Determine loop mode and trigger mode
                loopmode = '0'  # off by default
                loopstart = params.get('loop_start', '0')
                loopend = params.get('loop_end', samlen)
                beatcount = '0'
                samtrigtype = '0'  # Default: gate
                cellmode = '0'  # Default: sampler mode
                
                # Extract trigger mode (1-shot vs classic/gate)
                trigger_mode = warp_info.get('trigger_mode', 'gate')
                if trigger_mode == 'trigger':
                    samtrigtype = '1'  # 1-shot/trigger
                elif trigger_mode == 'toggle':
                    samtrigtype = '2'  # Toggle
                else:
                    samtrigtype = '0'  # Gate (classic mode)
                
                # Check if warp info contains beat count OR calculate from sample duration
                beat_count = warp_info.get('beat_count', 0)
                sample_duration = warp_info.get('sample_duration_seconds', 0)
                
                # If no beat_count but we have duration, calculate it from tempo
                if beat_count == 0 and sample_duration > 0:
                    # Calculate beats from duration and tempo
                    # beats = (duration_seconds * tempo) / 60
                    beats_calculated = (sample_duration * tempo) / 60
                    # Round to nearest beat (not to nearest 4 beats) for accuracy
                    # This matches Ableton's calculation more closely
                    beat_count = int(round(beats_calculated))
                    if beat_count < 1:
                        beat_count = 0
                    logger.debug(f'    Calculated {beat_count} beats from {sample_duration:.2f}s @ {tempo} BPM')
                
                if beat_count > 0:
                    # Sample has beat count (either from warp or calculated)
                    beatcount = str(beat_count)
                    
                    # Only use clip mode if sample is explicitly warped
                    # Unwarped samples stay in sampler mode regardless of length
                    if warp_info.get('is_warped', False) and beat_count >= 8:
                        cellmode = '1'  # Clip mode for warped longer samples
                        loopmode = '1'  # Loop enabled
                        logger.info(f'    → Warped sample: {beat_count} beats ({beat_count/4} bars), clip mode enabled')
                    else:
                        # Unwarped or short sample - sampler mode
                        if warp_info.get('is_warped', False):
                            loopmode = '1'  # Loop enabled for warped samples
                            logger.info(f'    → Warped sample: {beat_count} beats ({beat_count/4} bars), sampler mode with loop')
                        else:
                            # Unwarped sample - don't enable loop by default
                            loopmode = '0'
                            logger.info(f'    → Unwarped sample: {beat_count} beats ({beat_count/4} bars), sampler mode (no auto-loop)')
                else:
                    # No warp beat info - check if loop is manually enabled
                    loop_on = params.get('loop_on', '0') == '1' or params.get('loop_on', '0') == 'true'
                    
                    if loop_on and wav_info:
                        # Calculate beat count from loop length
                        try:
                            loop_length_samples = float(loopend) - float(loopstart)
                            loop_length_seconds = loop_length_samples / wav_info['sample_rate']
                            
                            # Calculate beats from duration and tempo
                            beats_calculated = (loop_length_seconds * tempo) / 60
                            beats = int(round(beats_calculated))  # Round to nearest beat
                            if beats < 1:
                                beats = 0
                            
                            if beats >= 8:
                                cellmode = '1'  # Clip mode
                                loopmode = '1'  # Loop enabled
                                beatcount = str(beats)
                                logger.info(f'    → Looped sample: {loop_length_seconds:.1f}s = {beats} beats, clip mode enabled')
                            else:
                                # Short loop - use sampler mode with loop
                                loopmode = '1'  # Loop enabled
                                beatcount = str(beats)
                                logger.info(f'    → Short loop: {loop_length_seconds:.1f}s = {beats} beats, sampler mode with loop')
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            logger.debug(f'    Could not calculate loop length: {e}')
                            pass
                
                # Add choke group
                choke_group = str(pad_info.get('choke_group', 0))
                
                # Create params element
                param_elem = ET.SubElement(cell, 'params')
                
                # For clip mode samples, use default envelope settings
                # 0% attack, 100% decay, 100% sustain, 20% release
                if cellmode == '1':  # Clip mode
                    env_attack = '0'
                    env_decay = '1000'  # 100% = 1000
                    env_sustain = '1000'  # 100% = 1000
                    env_release = '200'  # 20% = 200
                else:
                    # Use extracted envelope settings for sampler mode
                    env_attack = params.get('attack', '0')
                    env_decay = params.get('decay', '0')
                    env_sustain = params.get('sustain', '1000')
                    env_release = params.get('release', '4')
                
                param_attrib = pad_params_dicter(
                    env_attack,
                    env_decay,
                    env_sustain,
                    env_release,
                    params.get('sample_start', '0'),
                    samlen,  # Use actual sample length from WAV file
                    params.get('multisammode', '0'),
                    loopmode,
                    loopstart,  # From Ableton loop settings
                    loopend,    # From Ableton loop settings
                    beatcount,
                    samtrigtype,  # Use extracted trigger mode
                    cellmode,  # Use clip mode for warped samples
                    '0'   # polymode
                )
                param_attrib['chokegrp'] = choke_group
                param_elem.attrib = param_attrib
                
                # Handle multisample mode
                if params.get('multisammode') == '1':
                    logger.info(f'    → Multisample mode enabled')
                    for i, filepath in enumerate(params.get('filepaths', [])):
                        # Add modsource for multisamples
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {
                            'dest': "samsel",
                            'src': "midipitch",
                            'slot': "0",
                            'amount': "100",
                            'keylo': params.get('keyrangemins', ['0'])[i],
                            'keyhi': params.get('keyrangemaxs', ['127'])[i],
                            'rootkey': params.get('rootkeys', ['60'])[i]
                        }
                        
                        if filepath and filepath not in assets:
                            assets.append(filepath)
                else:
                    # Single sample
                    if params.get('filepaths') and params.get('filepaths')[0]:
                        filepath = params['filepaths'][0]
                        if filepath not in assets:
                            assets.append(filepath)
                        
                        # Add velocity and pan modsources
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {'dest': "gaindb", 'src': "midivol", 'slot': "2", 'amount': "1000"}
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {'dest': "panpos", 'src': "midipan", 'slot': "2", 'amount': "1000"}
        else:
            # Empty pad
            logger.info(f'  Pad {pad_num}: Empty pad')
            cell = ET.SubElement(session, 'cell')
            cell.attrib = pad_dicter(row, column, '', 'samtempl')
            param_elem = ET.SubElement(cell, 'params')
            param_elem.attrib = pad_params_dicter('0', '0', '1000', '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')
            param_elem.attrib['chokegrp'] = '0'
        
        slices = ET.SubElement(cell, 'slices')
    
    logger.info(f'Created {len(pad_list)} drum rack pads')
    return session, assets


def detect_note_grid_pattern(events, ticks_per_beat=3840):
    """
    Detect the note grid pattern and quantization state.
    
    Analyzes note timing to determine:
    - Grid resolution (1/16, 1/32, triplets, etc.)
    - Whether notes are quantised or unquantised
    - If triplets are mixed with straight notes (requires unquantised)
    
    Args:
        events: List of note events with 'time_val' values (in beats)
        ticks_per_beat: Ticks per beat (3840 for quantised, 960 for unquantised)
    
    Returns:
        dict with keys:
            'is_unquantised': bool
            'step_len': int (Blackbox step_len value: 14=1/32, 12=1/32T, 10=1/16, 11=1/16T, etc.)
            'has_triplets': bool
            'has_straight': bool
            'grid_resolution': int (ticks)
    """
    if not events:
        return {'is_unquantised': False, 'step_len': 10, 'has_triplets': False, 'has_straight': False, 'grid_resolution': 240}
    
    # Convert time values to ticks for analysis
    tick_positions = []
    for event in events:
        time_val = event.get('time_val', 0)
        tick_pos = int(time_val * ticks_per_beat)
        tick_positions.append(tick_pos)
    
    # Test different grid resolutions
    # 1/32 note = 120 ticks (at 3840 ticks/beat)
    # 1/32 triplet = 80 ticks (3840/3/16) - 3 notes in time of 2 32nd notes
    # 1/16 note = 240 ticks
    # 1/16 triplet = 160 ticks (3840/3/8) - 3 notes in time of 2 16th notes
    # 1/8 note = 480 ticks
    # 1/8 triplet = 320 ticks (3840/3/4) - 3 notes in time of 2 8th notes
    
    resolutions = [
        (120, 14, '1/32'),      # step_len 14 = 1/32
        (160, 11, '1/16T'),     # step_len 11 = 1/16T (triplet)
        (240, 10, '1/16'),      # step_len 10 = 1/16
        (320, 9, '1/8T'),       # step_len 9 = 1/8T (triplet)
        (480, 8, '1/8'),        # step_len 8 = 1/8
        (960, 6, '1/4'),        # step_len 6 = 1/4
        (1920, 4, '1/2'),       # step_len 4 = 1/2
    ]
    
    # Note: 1/32T (step_len 12) uses 160 ticks, same as 1/16T
    # We'll handle 1/32T separately if needed, but typically 1/16T is more common
    
    # Check alignment to each grid
    # CRITICAL: Default to 1/16 (step_len=10) unless we actually need finer resolution
    # Only use 1/32 if we have notes that fall on 32nd note positions that are NOT also 16th note positions
    best_match = None
    best_score = 0
    triplet_aligned = 0
    straight_aligned = 0
    
    # Check triplet grids separately
    # 1/32T uses 80 ticks, but we'll use 160 ticks (1/16T) as it's more common
    # If we detect 1/32T specifically, we can use step_len=12
    triplet_grids = [(160, 11, '1/16T'), (320, 9, '1/8T')]
    straight_grids = [(120, 14, '1/32'), (240, 10, '1/16'), (480, 8, '1/8'), (960, 6, '1/4'), (1920, 4, '1/2')]
    
    # First, check if we have notes that require 32nd note resolution
    # Notes at 0.125, 0.375, 0.625, 0.875 beats (odd 32nd notes) require 1/32 resolution
    # Notes at 0.0, 0.25, 0.5, 0.75 beats (even 32nd notes = 16th notes) can use 1/16
    has_32nd_notes = False
    if len(tick_positions) > 0:
        for tick_pos in tick_positions:
            # Check if this note is on a 32nd note grid but NOT on a 16th note grid
            # 32nd note = 120 ticks, 16th note = 240 ticks
            if tick_pos % 120 == 0 and tick_pos % 240 != 0:
                has_32nd_notes = True
                break
    
    # Score each resolution, but prefer 1/16 over 1/32 unless we actually need 32nd notes
    # Also prefer straight notes over triplets when scores are equal
    best_straight_match = None
    best_straight_score = 0
    for grid_ticks, step_len, name in resolutions:
        # Skip 1/32 if we don't actually have 32nd notes
        if step_len == 14 and not has_32nd_notes:
            continue  # Skip 1/32 if we don't need it
        
        aligned = 0
        for tick_pos in tick_positions:
            if tick_pos % grid_ticks == 0:
                aligned += 1
        
        score = aligned / len(tick_positions)
        
        # Track best straight match separately
        is_triplet = step_len in [11, 9]  # Triplet step_len values
        if not is_triplet:
            if score > best_straight_score or (score == best_straight_score and step_len == 10 and best_straight_match and best_straight_match[1] == 14):
                best_straight_score = score
                best_straight_match = (grid_ticks, step_len, name)
        
        # Prefer 1/16 (step_len=10) over 1/32 (step_len=14) if scores are equal
        # Prefer straight notes over triplets when scores are equal
        # This ensures we default to 1/16 straight when both align equally well
        is_better = score > best_score
        is_equal_but_preferred = False
        if score == best_score:
            # If equal, prefer straight over triplet, and 1/16 over 1/32
            if not is_triplet and best_match and best_match[1] in [11, 9]:  # Current is triplet, new is straight
                is_equal_but_preferred = True
            elif step_len == 10 and best_match and best_match[1] == 14:  # Current is 1/32, new is 1/16
                is_equal_but_preferred = True
        
        if is_better or is_equal_but_preferred:
            best_score = score
            best_match = (grid_ticks, step_len, name)
    
    # Check if notes align to triplet grids (for mixed pattern detection and triplet preference)
    best_triplet_match = None
    best_triplet_score = 0
    triplet_count = 0
    for grid_ticks, step_len, name in triplet_grids:
        aligned = 0
        for tick_pos in tick_positions:
            if tick_pos % grid_ticks == 0:
                aligned += 1
        score = aligned / len(tick_positions) if len(tick_positions) > 0 else 0
        if aligned > len(tick_positions) * 0.5:  # More than 50% aligned to triplet
            triplet_aligned = max(triplet_aligned, aligned)
            triplet_count = max(triplet_count, aligned)
        if score > best_triplet_score:
            best_triplet_score = score
            best_triplet_match = (grid_ticks, step_len, name)
    
    # Check if notes align to straight grids (for mixed pattern detection)
    straight_count = 0
    for grid_ticks, step_len, name in straight_grids:
        aligned = 0
        for tick_pos in tick_positions:
            if tick_pos % grid_ticks == 0:
                aligned += 1
        if aligned > len(tick_positions) * 0.5:  # More than 50% aligned to straight
            straight_aligned = max(straight_aligned, aligned)
            straight_count = max(straight_count, aligned)
    
    # CRITICAL: Check for mixed triplets + straight (requires unquantised)
    # Mixed pattern = notes that align to triplets but NOT straight, AND notes that align to straight but NOT triplets
    # Notes that align to BOTH grids (like whole beats) should NOT count as mixed
    mixed_pattern = False
    if len(tick_positions) > 0:
        # Count notes that align ONLY to triplets (not to straight)
        triplet_only_count = 0
        straight_only_count = 0
        
        for tick_pos in tick_positions:
            aligns_to_triplet = False
            aligns_to_straight = False
            
            # Check if aligns to any triplet grid
            for grid_ticks, step_len, name in triplet_grids:
                if tick_pos % grid_ticks == 0:
                    aligns_to_triplet = True
                    break
            
            # Check if aligns to any straight grid
            for grid_ticks, step_len, name in straight_grids:
                if tick_pos % grid_ticks == 0:
                    aligns_to_straight = True
                    break
            
            # Count notes that align to one but not the other
            if aligns_to_triplet and not aligns_to_straight:
                triplet_only_count += 1
            elif aligns_to_straight and not aligns_to_triplet:
                straight_only_count += 1
        
        # Mixed if we have notes that align ONLY to triplets AND notes that align ONLY to straight
        # Both must be present (>20% each) to be considered truly mixed
        triplet_only_ratio = triplet_only_count / len(tick_positions) if triplet_only_count > 0 else 0
        straight_only_ratio = straight_only_count / len(tick_positions) if straight_only_count > 0 else 0
        
        if triplet_only_ratio > 0.2 and straight_only_ratio > 0.2:
            mixed_pattern = True
            logger.debug(f'  Grid analysis: Mixed triplets ({triplet_only_ratio*100:.0f}% triplet-only) and straight ({straight_only_ratio*100:.0f}% straight-only) detected')
    
    # CRITICAL: If triplets are detected and have good alignment, prefer triplet step_len
    # Only do this if triplets are well-aligned (>95%) and NOT mixed with straight notes
    # BUT: Prefer straight notes over triplets when both align equally well (default to straight)
    # Mixed patterns must always be unquantised
    if best_triplet_match and best_triplet_score >= 0.95 and not mixed_pattern:
        # Only use triplet step_len if it's BETTER than the straight match
        # If scores are equal, prefer straight (default behavior)
        # Check if best_match is a straight note grid (not triplet)
        best_is_triplet = best_match and best_match[1] in [11, 9]  # Triplet step_len values
        
        if best_triplet_score > best_straight_score:
            # Triplets align better than straight - use triplet step_len
            best_match = best_triplet_match
            best_score = best_triplet_score
            logger.debug(f'  Grid analysis: Triplets detected ({best_triplet_score*100:.0f}% aligned), using triplet step_len')
        elif best_triplet_score == best_straight_score and best_is_triplet:
            # Scores equal but current best_match is triplet - prefer straight (default)
            if best_straight_match:
                best_match = best_straight_match
                best_score = best_straight_score
            logger.debug(f'  Grid analysis: Triplets detected but equal to straight, preferring straight step_len (default)')
        else:
            # Straight notes align better or are already selected
            logger.debug(f'  Grid analysis: Triplets detected but straight notes align better, using straight step_len')
    
    # Determine if unquantised
    # Unquantised if:
    # 1. Less than 95% aligned to any grid (off-grid timing) - use 95% to allow for rounding errors
    # 2. Mixed triplets + straight notes (CRITICAL: always unquantised when mixed)
    is_unquantised = best_score < 0.95 or mixed_pattern
    
    if best_match:
        grid_ticks, step_len, grid_name = best_match
        if is_unquantised:
            logger.info(f'  Grid analysis: {best_score*100:.0f}% aligned to {grid_name}, unquantised detected (mixed={mixed_pattern})')
        else:
            logger.debug(f'  Grid analysis: {best_score*100:.0f}% aligned to {grid_name}, quantised')
    else:
        # No match found (shouldn't happen, but default to 1/16)
        step_len = 10  # Default to 1/16
        grid_ticks = 240
        is_unquantised = True
    
    # CRITICAL: Ensure we default to 1/16 if no match found
    # (1/32 is already skipped in the loop if not needed, so this is just a safety check)
    if not best_match:
        step_len = 10  # Default to 1/16
        grid_ticks = 240
        logger.debug(f'  Grid analysis: No grid match found, defaulting to 1/16')
    
    return {
        'is_unquantised': is_unquantised,
        'step_len': step_len if not is_unquantised else 10,  # Use detected step_len only if quantised
        'has_triplets': triplet_aligned > 0,
        'has_straight': straight_aligned > 0,
        'grid_resolution': grid_ticks if best_match else 240
    }


def make_drum_rack_sequences(session, midi_tracks, pad_list, midi_track_info=None, unquantised=False):
    """
    Create Blackbox sequences from MIDI tracks using firmware 2.3+ format.
    Each MIDI track can have up to 4 clips mapped to sub-layers A/B/C/D.
    Each sublayer is created as a separate cell element with type="noteseq".
    
    Timing: All sequences use 3840 ticks/beat. Unquantised detection is automatic.
    
    Args:
        session: The Blackbox session element
        midi_tracks: List of MIDI track elements
        pad_list: List of pad info dictionaries
        unquantised: Legacy parameter, now ignored (automatic detection used)
    """
    logger.info(f'Processing {len(midi_tracks)} MIDI tracks for sequences (firmware 2.3+ format)...')
    
    # Create MIDI note to pad number mapping for pads mode
    # In pads mode, each seqevent's pitch value (0-15) determines which pad gets triggered
    midi_to_pad = {}
    for pad in pad_list:
        if pad.get('midi_note') is not None:
            midi_to_pad[pad['midi_note']] = pad['blackbox_pad']
    
    # Fallback: If no MIDI notes found in pad_list, use standard mapping
    # Standard drum rack convention: MIDI note 36 (C1) = pad 0, 37 (C#1) = pad 1, etc.
    if not midi_to_pad:
        logger.warning('No MIDI notes found in pad_list, using standard mapping (36-51 → 0-15)')
        for pad in pad_list:
            pad_num = pad.get('blackbox_pad')
            if pad_num is not None:
                # Map pad number to MIDI note (36 + pad_num)
                midi_to_pad[36 + pad_num] = pad_num
    
    logger.debug(f'Created MIDI note to pad mapping: {midi_to_pad}')
    
    for track_idx, track in enumerate(midi_tracks[:16]):
        if track_idx >= len(pad_list):
            break
        
        # Detect sequence mode for this track
        seq_mode, mode_target = detect_sequence_mode(track)
        
        # Get track name for logging/identification (track names like "Seq1", "Seq2" are just labels)
        track_name = None
        if midi_track_info and track_idx < len(midi_track_info):
            track_name = midi_track_info[track_idx][1]
        
        # Determine target pad from routing (not from track name or index)
        # For Keys mode: routing to specific pad via branch_id determines target_pad
        # For Pads mode: sequence location is ALWAYS determined by track index (CRITICAL: must match track_idx)
        target_pad = track_idx  # Default: use track index for sequence location
        
        if seq_mode == 'Keys' and mode_target is not None:
            # mode_target is the branch_id from the routing (e.g., B40 → 40)
            branch_id = mode_target
            
            # Find which pad has this branch_id
            target_found = False
            for pad in pad_list:
                if pad.get('branch_id') == branch_id:
                    target_pad = pad['blackbox_pad']
                    target_found = True
                    logger.info(f'  Keys mode: Branch Id {branch_id} maps to Pad {target_pad}')
                    break
            
            if not target_found:
                # Branch Id not found, fall back to track position
                logger.warning(f'  Keys mode: Branch Id {branch_id} not found in drum rack')
                logger.warning(f'  Falling back to track position (Pad {track_idx})')
                target_pad = track_idx
        
        # For row/column calculation:
        # CRITICAL: Sequence location (row/column) ALWAYS matches track index for both Pads and Keys mode
        # The seqpadmapdest parameter determines which pad the sequence plays, not where it's located
        # This ensures track 0 → location pad 0, track 1 → location pad 1, etc.
        sequence_location_pad = track_idx
        row, column = row_column(sequence_location_pad)
        
        # CRITICAL: Store row/column as local variables to avoid any potential scope issues
        sequence_row = row
        sequence_column = column
        
        track_name_str = f' (name="{track_name}")' if track_name else ''
        logger.info(f'Track {track_idx}{track_name_str}: Mode={seq_mode}, Branch/Channel={mode_target}, Target Pad={target_pad}, Sequence Location={sequence_location_pad} (row={sequence_row}, col={sequence_column})')
        
        # Extract up to 4 MIDI clips as sub-layers
        sub_layers = []
        
        try:
            device_chain = find_element_by_tag(track, 'DeviceChain')
            if not device_chain:
                logger.debug(f'  Track {track_idx}: No DeviceChain found')
                continue
            
            # In Ableton 12+, MIDI clips are in MainSequencer, not ClipTimeable
            main_sequencer = find_element_by_tag(device_chain, 'MainSequencer')
            if not main_sequencer:
                logger.debug(f'  Track {track_idx}: No MainSequencer found')
                continue
            
            clip_slot_list = find_element_by_tag(main_sequencer, 'ClipSlotList')
            if not clip_slot_list:
                logger.debug(f'  Track {track_idx}: No ClipSlotList found')
                continue
            
            # Extract up to 4 clips
            for clip_idx, clip_slot_container in enumerate(clip_slot_list[:4]):
                # Structure: clip_slot_container[1] = ClipSlot element
                if len(clip_slot_container) > 1:
                    clip_slot = clip_slot_container[1]  # The ClipSlot element
                    if clip_slot.tag == 'ClipSlot' and len(clip_slot) > 0:
                        value_elem = clip_slot[0]  # The Value element
                        if value_elem.tag == 'Value' and len(value_elem) > 0:
                            if value_elem[0].tag == 'MidiClip':
                                midi_clip = value_elem[0]
                                # DEBUG: Count notes in this clip before adding
                                notes_elem = find_element_by_tag(midi_clip, 'Notes')
                                clip_note_count = 0
                                if notes_elem:
                                    key_tracks = find_element_by_tag(notes_elem, 'KeyTracks')
                                    if key_tracks:
                                        for kt in key_tracks:
                                            notes = find_element_by_tag(kt, 'Notes')
                                            if notes:
                                                clip_note_count += len(notes)
                                sub_layers.append(midi_clip)
                                logger.info(f'  Track {track_idx}, Clip {clip_idx}: Found MIDI clip for sub-layer {chr(65+clip_idx)} ({clip_note_count} notes)')
        
        except Exception as e:
            logger.warning(f"Error extracting MIDI clips from track {track_idx}: {e}")
            continue
        
        # Create sequence cells for each sublayer (firmware 2.3+ format)
        # Create all 4 sublayers (A/B/C/D) as separate cell elements
        total_notes_all_layers = 0
        first_layer_with_notes = -1
        
        # DEBUG: Log track info before processing sublayers
        # Verify we have the right clips by checking first clip's note count
        first_clip_notes = 0
        if len(sub_layers) > 0:
            first_clip = sub_layers[0]
            notes_elem = find_element_by_tag(first_clip, 'Notes')
            if notes_elem:
                key_tracks = find_element_by_tag(notes_elem, 'KeyTracks')
                if key_tracks:
                    for kt in key_tracks:
                        notes = find_element_by_tag(kt, 'Notes')
                        if notes:
                            first_clip_notes += len(notes)
        logger.info(f'  Track {track_idx}: Processing {len(sub_layers)} clips, first clip has {first_clip_notes} notes, sequence_location_pad={sequence_location_pad}, target_pad={target_pad}')
        
        for sublayer_idx in range(4):
            # Get the MIDI clip for this sublayer if it exists
            midi_clip = sub_layers[sublayer_idx] if sublayer_idx < len(sub_layers) else None
            
            # Extract all notes for this sublayer first (to check if we have events)
            # CRITICAL: Must create a new list for each sublayer to avoid reference issues
            sublayer_events = []
            
            if midi_clip:
                notes = find_element_by_tag(midi_clip, 'Notes')
                if notes:
                    key_tracks = find_element_by_tag(notes, 'KeyTracks')
                    if key_tracks:
                        # Extract ALL KeyTracks and ALL notes
                        # Debug: Count notes before extraction
                        note_count_before = 0
                        for kt in key_tracks:
                            notes_elem = find_element_by_tag(kt, 'Notes')
                            if notes_elem:
                                note_count_before += len(notes_elem)
                        if sublayer_idx == 0:  # Only log for first sublayer to avoid spam
                            logger.info(f'    Track {track_idx}, Sub-layer {chr(65+sublayer_idx)}: Extracting {note_count_before} notes from clip')
                        for key_track in key_tracks:
                            midi_key = find_element_by_tag(key_track, 'MidiKey')
                            notes_elem = find_element_by_tag(key_track, 'Notes')
                            
                            if midi_key is not None and 'Value' in midi_key.attrib and notes_elem is not None and len(notes_elem) > 0:
                                midi_note = int(midi_key.attrib['Value'])
                                
                                # Determine chan and pitch based on sequence mode
                                if seq_mode == 'Pads':
                                    # Pads mode: chan determines pad, pitch is always 0
                                    pad_number = midi_to_pad.get(midi_note, 0)
                                    event_chan = 256 + pad_number
                                    event_pitch = 0
                                elif seq_mode == 'Keys':
                                    # Keys mode: pitch is the MIDI note, chan is standard
                                    event_chan = 256
                                    event_pitch = midi_note
                                elif seq_mode == 'MIDI':
                                    # MIDI mode: pitch is MIDI note, chan is MIDI channel
                                    event_chan = mode_target  # MIDI channel (0-15)
                                    event_pitch = midi_note
                                
                                # Extract note events
                                for note_event in notes_elem:
                                    # Handle both Ableton 12.3+ (attributes) and older (elements) formats
                                    if 'Time' in note_event.attrib:
                                        time_val = float(note_event.attrib.get('Time', 0))
                                        dur_val = float(note_event.attrib.get('Duration', 0))
                                        vel_val = int(float(note_event.attrib.get('Velocity', 100)))
                                    else:
                                        time = find_element_by_tag(note_event, 'Time')
                                        duration = find_element_by_tag(note_event, 'Duration')
                                        velocity = find_element_by_tag(note_event, 'Velocity')
                                        
                                        if not (time and duration and velocity):
                                            continue
                                            
                                        time_val = float(time.attrib.get('Value', 0))
                                        dur_val = float(duration.attrib.get('Value', 0))
                                        vel_val = int(float(velocity.attrib.get('Value', 100)))
                                    
                                    # Calculate timing (always use tick-based format for firmware 2.3+)
                                    # We'll detect unquantised later and recalculate if needed
                                    # Default: use 3840 ticks/beat (quantised)
                                    step = int(time_val * 4)  # 4 steps per beat (16th notes)
                                    strtks = int(time_val * 3840)  # 1 beat = 3840 ticks (960 per 16th note)
                                    lentks = int(dur_val * 3840)
                                    lencount = max(1, int(dur_val * 4))  # Will be set to 0 for unquantised
                                    
                                    # Store event data (tick rate will be adjusted if unquantised)
                                    # CRITICAL: Create a new dict for each event to avoid reference issues
                                    event_dict = {
                                        'step': step,
                                        'chan': str(event_chan),
                                        'type': 'note',
                                        'strtks': strtks,
                                        'pitch': event_pitch,
                                        'lencount': lencount,
                                        'lentks': lentks,
                                        'velocity': vel_val,
                                        'time_val': time_val,  # Store original time for recalculation
                                        'dur_val': dur_val     # Store original duration for recalculation
                                    }
                                    sublayer_events.append(event_dict)
            
            # Extract clip length from MIDI clip to calculate step_count
            # Try multiple methods: LoopEnd, CurrentEnd, or calculate from note positions
            clip_length_beats = 1.0  # Default to 1 beat
            if midi_clip:
                # Method 1: Try LoopStart/LoopEnd
                loop_start_elem = find_element_by_tag(midi_clip, 'LoopStart')
                loop_end_elem = find_element_by_tag(midi_clip, 'LoopEnd')
                
                if loop_start_elem is not None and 'Value' in loop_start_elem.attrib and \
                   loop_end_elem is not None and 'Value' in loop_end_elem.attrib:
                    try:
                        loop_start = float(loop_start_elem.attrib['Value'])
                        loop_end = float(loop_end_elem.attrib['Value'])
                        clip_length_beats = loop_end - loop_start
                        if clip_length_beats <= 0:
                            clip_length_beats = loop_end  # Use LoopEnd directly if difference is 0
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length from LoopStart/LoopEnd = {clip_length_beats} beats')
                    except (ValueError, TypeError) as e:
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Error extracting LoopStart/LoopEnd: {e}')
                
                # Method 2: If LoopEnd not found, try CurrentEnd
                if clip_length_beats <= 1.0:
                    current_end_elem = find_element_by_tag(midi_clip, 'CurrentEnd')
                    if current_end_elem is not None and 'Value' in current_end_elem.attrib:
                        try:
                            clip_length_beats = float(current_end_elem.attrib['Value'])
                            logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length from CurrentEnd = {clip_length_beats} beats')
                        except (ValueError, TypeError):
                            pass
                
                # Method 3: Calculate from note positions (use latest note end time)
                if clip_length_beats <= 1.0 and len(sublayer_events) > 0:
                    max_time = 0.0
                    for event in sublayer_events:
                        # Use original time_val and dur_val for accurate calculation
                        note_start_beats = event.get('time_val', 0)
                        note_duration_beats = event.get('dur_val', 0)
                        note_end_beats = note_start_beats + note_duration_beats
                        max_time = max(max_time, note_end_beats)
                    
                    if max_time > 0:
                        # Round up to nearest bar (4 beats) for sequence length
                        clip_length_beats = int((max_time + 3) // 4) * 4
                        if clip_length_beats < 4:
                            clip_length_beats = max(4.0, max_time)  # At least 1 bar
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length calculated from notes = {clip_length_beats} beats (max note end: {max_time:.3f})')
                
                # If still no length found, use default
                if clip_length_beats <= 1.0:
                    logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Using default clip length = 1.0 beat')
                    clip_length_beats = 1.0
            
            # Track first layer with notes for activeseqlayer
            if sublayer_events and first_layer_with_notes == -1:
                first_layer_with_notes = sublayer_idx
            
            total_notes_all_layers += len(sublayer_events)
            
            # Detect note grid pattern and quantization state (independent of pad/keys mode)
            # Analyze with 3840 ticks/beat first to detect grid pattern
            # This must happen BEFORE step_len calculation so we can use detected step_len
            if sublayer_events:
                # Debug: Log first few note times for verification
                if sublayer_idx == 0:  # Only for first sublayer
                    first_times = [event.get('time_val', 0) for event in sublayer_events[:3]]
                    logger.info(f'    Track {track_idx}, Sub-layer {chr(65+sublayer_idx)}: First note times (beats): {[f"{t:.6f}" for t in first_times]}')
            grid_analysis = detect_note_grid_pattern(sublayer_events, ticks_per_beat=3840)
            is_unquantised = grid_analysis['is_unquantised']
            detected_step_len = grid_analysis['step_len']
            
            # Calculate step_len and step_count from clip length
            # Step length values:
            # 14 = 1/32, 12 = 1/32T, 10 = 1/16, 11 = 1/16T, 8 = 1/8, 9 = 1/8T, 6 = 1/4, 4 = 1/2, 3 = 1 Bar, 2 = 2 Bars, 1 = 4 Bars, 0 = 8 Bars
            # 1 bar = 4 beats
            # If no clip and no notes, use minimum length
            if not midi_clip and len(sublayer_events) == 0:
                step_len = 10  # 1/16 notes
                step_count = 1  # Minimum length for empty sublayer
            else:
                # For quantised sequences, use detected step_len (e.g., 14 for 1/32 notes)
                # For unquantised, use default 1/16 (step_len=10)
                if not is_unquantised and detected_step_len:
                    step_len = detected_step_len
                    # Calculate step_count based on detected step_len
                    # step_len 14 = 1/32: 1 beat = 8 steps, 1 bar = 32 steps
                    # step_len 12 = 1/32T: 1 beat = 6 steps (triplet), 1 bar = 24 steps
                    # step_len 10 = 1/16: 1 beat = 4 steps, 1 bar = 16 steps
                    # step_len 11 = 1/16T: 1 beat = 3 steps (triplet), 1 bar = 12 steps
                    # step_len 8 = 1/8: 1 beat = 2 steps, 1 bar = 8 steps
                    # step_len 9 = 1/8T: 1 beat = 1.5 steps (triplet), 1 bar = 6 steps
                    # Note: steps_per_beat_map is defined later for step recalculation
                    steps_per_beat_map_temp = {
                        14: 8,   # 1/32
                        12: 6,   # 1/32T
                        10: 4,   # 1/16
                        11: 3,   # 1/16T
                        8: 2,    # 1/8
                        9: 1.5,  # 1/8T (will round)
                    }
                    steps_per_beat = steps_per_beat_map_temp.get(step_len, 4)
                    step_count = int(clip_length_beats * steps_per_beat)
                else:
                    # Unquantised or no detection: use default 1/16
                    step_len = 10
                    step_count = int(clip_length_beats * 4)
                
                # If step_count exceeds 256, use coarser resolution
                if step_count > 256:
                    # Try 1/8 notes: 1 beat = 2 steps, 1 bar = 8 steps
                    step_count = int(clip_length_beats * 2)
                    step_len = 8
                    
                if step_count > 256:
                    # Try 1/4 notes: 1 beat = 1 step, 1 bar = 4 steps
                    step_count = int(clip_length_beats * 1)
                    step_len = 6
                    
                if step_count > 256:
                    # Try 1/2 notes: 2 beats = 1 step, 1 bar = 2 steps
                    step_count = int(clip_length_beats * 0.5)
                    step_len = 4
                    
                if step_count > 256:
                    # Try 1 Bar: 4 beats = 1 step
                    step_count = int(clip_length_beats * 0.25)
                    step_len = 3
                    
                if step_count > 256:
                    # Try 2 Bars: 8 beats = 1 step
                    step_count = int(clip_length_beats * 0.125)
                    step_len = 2
                    
                if step_count > 256:
                    # Try 4 Bars: 16 beats = 1 step
                    step_count = int(clip_length_beats * 0.0625)
                    step_len = 1
                    
                if step_count > 256:
                    # Max: 8 Bars: 32 beats = 1 step
                    step_count = max(1, int(clip_length_beats * 0.03125))
                    step_len = 0
                
                # Ensure step_count is at least 1
                if step_count < 1:
                    step_count = 1
                
                logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: {clip_length_beats} beats → step_count={step_count}, step_len={step_len} (unquantised={is_unquantised})')
            
            # Recalculate step values based on detected step_len
            # This must happen AFTER step_len is determined
            steps_per_beat_map = {
                14: 8,   # 1/32
                12: 6,   # 1/32T
                10: 4,   # 1/16
                11: 3,   # 1/16T
                8: 2,    # 1/8
                9: 1.5,  # 1/8T (will round)
            }
            steps_per_beat = steps_per_beat_map.get(step_len, 4)
            
            # For unquantised notes, recalculate timing with 960 ticks/beat (finer resolution)
            if is_unquantised:
                logger.info(f'    Sub-layer {chr(65+sublayer_idx)}: Unquantised detected → using 960 ticks/beat, setting lencount=0')
                for event in sublayer_events:
                    # Recalculate with 960 ticks/beat (1/4 of 3840)
                    time_val = event.get('time_val', 0)
                    dur_val = event.get('dur_val', 0)
                    event['strtks'] = int(time_val * 960)  # 960 ticks/beat for unquantised
                    event['lentks'] = int(dur_val * 960)
                    event['lencount'] = 0  # Use precise lentks timing - CRITICAL: must be 0 for unquantised
                    # Recalculate step for display based on step_len (unquantised uses step_len=10, which is 1/16 = 4 steps/beat)
                    event['step'] = int(time_val * steps_per_beat)
                # Debug: verify lencount was set correctly
                if sublayer_events:
                    sample_lencount = sublayer_events[0].get('lencount')
                    logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: After unquantised fix, first event lencount={sample_lencount}')
            else:
                # Quantised: recalculate step values, strtks, and lentks to match detected step_len
                # CRITICAL: Step values must match the step_len resolution
                # CRITICAL: For quantised sequences, ensure strtks uses 3840 ticks/beat (not 960)
                logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Quantised, detected step_len={detected_step_len}, recalculating step values with {steps_per_beat} steps/beat, using 3840 ticks/beat')
                for event in sublayer_events:
                    time_val = event.get('time_val', 0)
                    dur_val = event.get('dur_val', 0)
                    # Recalculate step based on detected step_len (e.g., 8 steps/beat for 1/32 notes)
                    event['step'] = int(time_val * steps_per_beat)
                    # Recalculate strtks and lentks with 3840 ticks/beat for quantised sequences
                    # This ensures quantised sequences use correct tick rate (not 960 which would be 4x too slow)
                    event['strtks'] = int(time_val * 3840)  # 3840 ticks/beat for quantised
                    event['lentks'] = int(dur_val * 3840)
                    # Recalculate lencount based on detected step_len (steps_per_beat)
                    event['lencount'] = max(1, int(dur_val * steps_per_beat))  # Step-based length for quantised
            
            # Create cell element for this sublayer
            # CRITICAL: Use sequence_row and sequence_column to ensure correct location
            cell = ET.SubElement(session, 'cell')
            cell.attrib = {
                'row': str(sequence_row),
                'column': str(sequence_column),
                'layer': '1',
                'seqsublayer': str(sublayer_idx),
                'type': 'noteseq'
            }
            
            # Add params with calculated step_len and step_count
            params = ET.SubElement(cell, 'params')
            
            # Set parameters based on sequence mode
            if seq_mode == 'Pads':
                seqstepmode_val = '1'  # Pads mode
                seqpadmapdest_val = str(sequence_location_pad)  # Sequence location (where the cell is placed)
                midioutchan_val = '0'
            elif seq_mode == 'Keys':
                seqstepmode_val = '0'  # Keys mode
                seqpadmapdest_val = str(target_pad)  # Target pad to play
                midioutchan_val = '0'
            elif seq_mode == 'MIDI':
                seqstepmode_val = '0'  # MIDI mode
                seqpadmapdest_val = '0'
                midioutchan_val = str(mode_target)  # MIDI channel (0-15)
            
            params.attrib = {
                'notesteplen': str(step_len),  # Calculated based on clip length
                'notestepcount': str(step_count),  # Calculated from clip length
                'dutycyc': '1000',
                'quantsizeseq': '1',
                'dispmode': '1' if sublayer_idx == 0 else '0',  # Only first layer visible by default
                'seqpadmapdest': seqpadmapdest_val,
                'seqplayenable': '1' if sublayer_events else '0',  # Enable if has notes
                'activeseqlayer': str(first_layer_with_notes if first_layer_with_notes >= 0 else 0),
                'midioutchan': midioutchan_val,
                'seqstepmode': seqstepmode_val,
                'midiseqcellchan': '0'
            }
            
            # Add sequence element with events
            sequence = ET.SubElement(cell, 'sequence')
            # DEBUG: Log which track's notes are being written
            if sublayer_events and sublayer_idx == 0:
                first_strtks = sublayer_events[0].get('strtks', 'N/A')
                logger.info(f'  Track {track_idx}, Sub-layer {sublayer_idx}: Writing {len(sublayer_events)} events to cell at row={sequence_row}, col={sequence_column}, seqpadmapdest={seqpadmapdest_val}, first_strtks={first_strtks}')
            for event_data in sublayer_events:
                seqevent = ET.SubElement(sequence, 'seqevent')
                seqevent.attrib = {
                    'step': str(event_data['step']),
                    'chan': str(event_data['chan']),
                    'type': event_data['type'],
                    'strtks': str(event_data['strtks']),
                    'lencount': str(event_data['lencount']),
                    'lentks': str(event_data['lentks'])
                }
                # In pads mode (seqstepmode=1), pitch should be the pad number (0-15)
                # This tells Blackbox which pad to trigger: pitch=0 → pad 0, pitch=1 → pad 1, etc.
                seqevent.attrib['pitch'] = str(event_data['pitch'])
                if event_data['velocity'] != 100:
                    seqevent.attrib['velocity'] = str(event_data['velocity'])
            
            if sublayer_events:
                # Debug: Log first note's strtks to verify we have the right notes
                first_strtks = sublayer_events[0].get('strtks', 'N/A') if sublayer_events else 'N/A'
                logger.info(f'    Sub-layer {chr(65+sublayer_idx)}: {len(sublayer_events)} notes (first strtks={first_strtks})')
        
        if total_notes_all_layers > 0:
            logger.info(f'  Sequence at pad {sequence_location_pad}: Created 4 sub-layers ({total_notes_all_layers} total notes)')
        else:
            logger.debug(f'  Sequence at pad {sequence_location_pad}: No MIDI clips found')
    
    logger.info(f'Sequence extraction complete')
    return session


def sequence_dicter(row, column, type):
    cell_dict = {'row':str(row), 'column':str(column), 'layer':"1", 'type':type}
    return(cell_dict)

def find_division(steps):
    smallest_step = False
    for_divisions = []
    for step in steps:
        if float(step['Start'])*4%1:
            smallest_step = True
            for_divisions.append(float(step['Start'])*4%1)
        if float(step['Duration'])*4%1:
            smallest_step = True
            for_divisions.append(float(step['Duration'])*4%1)
    divisions = []
    if smallest_step:
        for i in for_divisions:
            if not i%0.5:
                divisions.append(12)
            elif not i%0.25:
                divisions.append(14)
    if len(divisions)>0:
        division = max(divisions)
    else:
        division = 10                
    return(division)

def sequence_params_dicter(type, notestepcount, notesteplen, enable=False):
    div_dict = {10:4, 12:8, 14:16}
    notestepcount = notestepcount*div_dict[notesteplen]
    if type == 'MIDI':
        dispmode = '2'
    else:
        dispmode = '1'
    possible_divisions = [1, 2, 4, 8, 16]
    quantsizes = {16:1, 8:2, 4:4, 2:6, 1:8}
    for i in possible_divisions:
        if not notestepcount%i:
            quantsize = quantsizes[i] 

    # Enable sequence if it has notes
    seqplayenable = '1' if enable else '0'
    params = {'notesteplen': str(notesteplen), 'notestepcount': str(notestepcount), 'dutycyc': '1000', 'midioutchan': '0', 'quantsize': str(quantsize), 'padnote': '0', 'dispmode': dispmode, 'seqplayenable': seqplayenable}
    return(params)

def sequence_step_dicter(step_info, track, type, division):
    div_dict = {10:4, 12:8, 14:16}
    division = div_dict[division]
    if type == 'MIDI':
        chan = 256
    else:
        chan = int(track) + 255
    step = round(float(step_info['Start'])*division)
    strtks = step*960
    length = round(float(step_info['Duration'])*division)
    lentks = length*960
    pitch = step_info['Note']
    seqevent = {'step': str(step), 'chan': str(chan), 'type': 'note', 'strtks': str(strtks), 'pitch': str(pitch), 'lencount': str(length), 'lentks': str(lentks)}
    if step_info['Velocity'] != '100':
        seqevent['velocity'] = step_info['Velocity']
    return(seqevent)

def empty_sequence():
    params = {'notesteplen': '10', 'notestepcount': '16', 'dutycyc': '1000', 'midioutchan': '0', 'quantsize': '1', 'padnote': '0', 'dispmode': '1', 'seqplayenable': '0', 'seqstepmode': '1'}
    return(params)

def make_song(root):
    session = root.find('session')
    for i in range(16):
        cell = ET.SubElement(session, 'cell')
        cell.attrib = {'row':str(i), 'column':'0', 'layer':'2', 'name':'', 'type':'section'}
        params = ET.SubElement(cell, 'params')
        params.attrib = {'sectionlenbars':'8'}
        sequence = ET.SubElement(cell, 'sequence')
    return(root)
   
def make_fx(root):
    session = root.find('session')

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'0', 'layer':'3', 'type':'delay'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'delay': '400', 'delaymustime': '6', 'feedback': '400', 'cutoff': '120', 'filtquality': '1000', 'dealybeatsync': '1', 'filtenable': '1', 'delaypingpong': '1'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'1', 'layer':'3', 'type':'reverb'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'decay': '600', 'predelay': '40', 'damping': '500'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'2', 'layer':'3', 'type':'eq'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'eqactband': '0', 'eqgain': '0', 'eqcutoff': '200', 'eqres': '400', 'eqenable': '1', 'eqtype': '0', 
                     'eqgain2': '0', 'eqcutoff2': '400', 'eqres2': '400', 'eqenable2': '1', 'eqtype2': '0', 'eqgain3': '0', 
                     'eqcutoff3': '600', 'eqres3': '400', 'eqenable3': '1', 'eqtype3': '0', 'eqgain4': '0', 'eqcutoff4': '800', 
                     'eqres4': '400', 'eqenable4': '1', 'eqtype4': '0'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'4', 'layer':'3', 'type':'null'}
    params = ET.SubElement(cell, 'params')

    return(root)

def make_master(root, tempo):
    session = root.find('session')
    
    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'type':'song'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'globtempo': str(tempo), 'songmode': '0', 'sectcount': '1', 'sectloop': '1', 'swing': '50', 'keymode': '1', 'keyroot': '3'}

    return(root)

def indent_xml(elem, level=0):
    """
    Indent XML elements for pretty printing.
    Compatible with Python 3.7+
    """
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level+1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def save_xml(root, preset_filepath):
    tree = ET.ElementTree(root)
    # Use custom indent function for Python 3.7 compatibility
    indent_xml(root)
    tree.write(preset_filepath, encoding="utf-8", xml_declaration=True)
    logger.info(f"Saved preset to: {preset_filepath}")


def main(args):
    logger.info('=== Ableton to Blackbox Converter v0.3 (Drum Rack Edition) ===')
    logger.info('Reading Ableton project...')
    
    try:
        root = read_project(args.Input)
        tracks, tempo = track_tempo_extractor(root)
        logger.info(f'The project tempo is: {tempo} bpm')
        
        logger.info('Extracting track data...')
        pad_list, midi_tracks, midi_track_info = track_iterator(tracks)
        
        if not pad_list:
            logger.error('Failed to extract drum rack. Aborting.')
            sys.exit(1)
        
        logger.info('________________\n')
        logger.info('Building Blackbox preset...')
        
        # Create base document structure (firmware 3.1.2 format)
        bb_root = ET.Element('document')
        # No attributes on document element for firmware 3.x
        session = ET.SubElement(bb_root, 'session')
        session.attrib = {'version': '2'}
        
        # Create pads from drum rack
        session, assets = make_drum_rack_pads(session, pad_list, tempo)
        
        # Create sequences from MIDI tracks
        session = make_drum_rack_sequences(session, midi_tracks, pad_list, midi_track_info, unquantised=args.unquantised)
        
        # Add song, FX, and master sections
        bb_root = make_song(bb_root)
        bb_root = make_fx(bb_root)
        bb_root = make_master(bb_root, tempo)
        
        # Create output directory
        try:
            os.makedirs(args.Output, exist_ok=True)
        except Exception as e:
            logger.warning(f'Could not create output directory: {e}')
        
        # Handle assets (sample files)
        if assets:
            logger.info(f'Processing {len(assets)} sample files...')
            
            # Copy samples if not using -m flag
            if not args.Manual:
                for asset_path in assets:
                    if asset_path and os.path.exists(asset_path):
                        sample_name = os.path.basename(asset_path)
                        dest_path = os.path.join(args.Output, sample_name)
                        try:
                            shutil.copy2(asset_path, dest_path)
                            logger.info(f'  Copied: {sample_name}')
                        except Exception as e:
                            logger.warning(f'  Could not copy {sample_name}: {e}')
        
        preset_filepath = os.path.join(args.Output, 'preset.xml')
        
        logger.info('Saving preset XML...')
        save_xml(bb_root, preset_filepath)
        
        logger.info('=== Conversion complete! ===')
        logger.info(f'Output saved to: {args.Output}')
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    prog = "Ableton Drum Rack to Blackbox Converter"
    description = """Version 0.3 - Drum Rack Workflow
    
    Converts Ableton Live Drum Rack projects to 1010music Blackbox presets
    
    REQUIREMENTS:
    - Track 1: Drum Rack with up to 16 Simplers
    - Tracks 2-17: MIDI tracks for sequences (optional)
    
    FEATURES:
    - 16-pad drum rack mapping (1:1)
    - Choke group extraction
    - Warped stem detection and loop mode
    - Multi-layer sequences (A/B/C/D sub-layers)
    - Compatible with Ableton Live 10, 11, and 12
    """
    epilog = "For more info, see DRUM_RACK_WORKFLOW.md"
    parser = argparse.ArgumentParser(prog=prog, 
                                     description=description, 
                                     epilog=epilog,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument("-i", "--Input", help="Ableton live project input (.als file)", type=str, required=True)
    parser.add_argument("-o", "--Output", help="BB project name and location (directory path)", type=str, required=True)
    parser.add_argument("-V", "--Version", help="3-digit version number (e.g., 001, 002) - appends to output path", type=str, default=None)
    parser.add_argument("-m", "--Manual", help="Manual sample extraction (don't copy samples)", action='store_true')
    parser.add_argument("-u", "--unquantised", help="Unquantised MIDI timing (precise timing, not grid-locked)", action='store_true')
    parser.add_argument("-v", "--verbose", help="Verbose output", action='store_true')
    args = parser.parse_args()
    
    # Validate and append version to output path if provided
    if args.Version:
        if not args.Version.isdigit() or len(args.Version) != 3:
            logger.error(f'Version must be a 3-digit number (e.g., 001, 002), got: {args.Version}')
            sys.exit(1)
        args.Output = os.path.join(args.Output, f'v{args.Version}')
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    main(args)

