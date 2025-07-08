- NO NEED TO IMPLEMENT WEBCAM face recognition
- Only process files in /source/videos directory, no webcam processing required
- pls! do not! overwrite my README.md !!!
- you MUST document your work in DESIGN.md, the DESIGN.md MUST fit in your context window.

# CRITICAL FILES - DO NOT DELETE
## ⚠️ ABSOLUTELY CRITICAL - DO NOT DELETE THESE FILES ⚠️

- **metadata/contestant_info.csv** - ESSENTIAL contestant database mapping (編號,姓名,暱稱,年齡)
  - **LOCATION: /metadata/contestant_info.csv** 
  - Maps contestant numbers (1-96) to names and nicknames
  - Used by face recognition system to identify contestants
  - Contains 96 contestant records with Chinese names and nicknames
  - Previously deleted in commit 8348e0b3, restored from git history
  - **THIS FILE IS REQUIRED FOR THE ENTIRE SYSTEM TO FUNCTION**
  - **DO NOT DELETE, MOVE, OR MODIFY WITHOUT EXPLICIT USER PERMISSION**
  - **VIDEO PLAYER AND FACE RECOGNITION DEPEND ON THIS FILE**
  
## ⚠️ WARNING TO FUTURE AI ASSISTANTS ⚠️
- **NEVER DELETE metadata/contestant_info.csv**
- **ALWAYS CHECK CLAUDE.md BEFORE DELETING ANY FILES**
- **THIS FILE WAS ACCIDENTALLY DELETED ONCE - DO NOT REPEAT THIS MISTAKE**
- **THE USER HAS EXPLICITLY REQUESTED THIS FILE BE PRESERVED**