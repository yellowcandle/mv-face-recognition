---
id: task-007
title: Update the title of the videos in the metadata to the actual Chinese titles
status: Done
assignee:
  - '@claude'
created_date: '2025-07-15'
updated_date: '2025-07-15'
labels: []
dependencies: []
---

## Description

Update the MOCK_VIDEOS array in the worker to use proper Chinese titles instead of generic video names, expanding from 2 videos to 5 videos with the specified Chinese titles.

## Implementation Plan

1. Update MOCK_VIDEOS array in worker/index.js
2. Add 3 additional video entries (videos 3, 4, 5)
3. Update all video titles to match the specified Chinese titles
4. Deploy and verify the changes

## Implementation Notes

Successfully updated the video titles in the MOCK_VIDEOS array to use proper Chinese titles.

**Files modified:**
- `/worker/index.js` - Updated MOCK_VIDEOS array with proper Chinese titles

**Key changes:**
- Expanded MOCK_VIDEOS from 2 to 5 videos 
- Updated all video titles to use proper Chinese titles as specified
- Added appropriate metadata (duration, upload dates, etc.) for new videos
- Maintained existing video IDs and structure

**Verification:**
- ✅ All 5 videos now have proper Chinese titles
- ✅ API endpoint `/api/videos` returns updated titles
- ✅ System deployed and working correctly

## Successful Criteria

✅ The titles have been successfully mapped as:
- video 1 → 《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅
- video 2 → 《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅  
- video 3 → 《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅
- video 4 → 《全民造星IV》極限拍MV
- video 5 → 《全民造星IV》播前熱身！率先表演《前傳》
