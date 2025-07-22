#!/usr/bin/env python3
import json

def analyze_recognition_results():
    with open('metadata/test-video-mv2_metadata.json', 'r') as f:
        data = json.load(f)
        
    # Extract unique recognized contestants
    recognized = set()
    frames_with_recognition = 0
    total_frames = len(data.get('frames', []))
    confidence_scores = []

    for frame in data.get('frames', []):
        if frame.get('recognitions'):
            frames_with_recognition += 1
            for rec in frame['recognitions']:
                if rec.get('contestant_name') and rec['contestant_name'] != 'Unknown':
                    recognized.add(rec['contestant_name'])
                    if rec.get('confidence'):
                        confidence_scores.append(rec['confidence'])
                    
    print('=== Face Recognition Analysis ===')
    print(f'Total frames processed: {total_frames}')
    print(f'Frames with recognitions: {frames_with_recognition}')
    print(f'Recognition rate: {frames_with_recognition/total_frames*100:.1f}%')
    print(f'Unique contestants recognized: {len(recognized)}')
    
    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        print(f'Average confidence: {avg_confidence:.3f}')
        print(f'Min confidence: {min(confidence_scores):.3f}')
        print(f'Max confidence: {max(confidence_scores):.3f}')
    
    print('\nRecognized contestants:')
    for contestant in sorted(list(recognized)):
        print(f'  - {contestant}')

if __name__ == '__main__':
    analyze_recognition_results()